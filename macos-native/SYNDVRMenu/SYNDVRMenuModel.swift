import AppKit
import Foundation
import SwiftUI

// SYN_DVR_DASHBOARD_320
// Read-only inspection of the one engine 3.1 job queue, except explicit
// cancellation/deletion requests. Does not touch FFmpeg, VLC or the pool.
private struct DVRJobFile: Decodable {
    let channel: String
    let title: String
    let start: Double
    let end: Double
    let folder: String
}

private struct DVRPartFile: Decodable {
    let bytes: Int64?
}

private struct DVRStatusFile: Decodable {
    let state: String
    let startedAt: Double?
    let finishedAt: Double?
    let error: String?
    let warning: String?
    let outputPath: String?
    let retryAt: Double?
    let retries: Int?
    let updatedAt: Double?
    let receivedBytes: Int64?
    let parts: [DVRPartFile]?
}

private struct DVRHeartbeat: Decodable {
    let timestamp: Double
    let pid: Int32
}

private struct DVRPoolStatus: Decodable {
    let timestamp: Double
    let occupied: Int
    let maxConnections: Int
}

struct MenuDVRJob: Identifiable {
    let id: String
    let channel: String
    let title: String
    let start: Date
    let end: Date
    let folder: String
    let state: String
    let startedAt: Date?
    let finishedAt: Date?
    let updatedAt: Date?
    let retryAt: Date?
    let receivedBytes: Int64
    let parts: Int
    let error: String?
    let warning: String?
    let outputPath: String?
    let signalGrowing: Bool
    let cancellationRequested: Bool

    var isTerminal: Bool {
        ["finished", "completed", "failed", "cancelled", "expired", "partial"].contains(state)
    }
    var isActive: Bool {
        ["recording", "reconnecting", "retrying", "waiting_for_tuner", "stopping"].contains(state)
    }
    var canCancel: Bool {
        ["scheduled", "programada", "recording", "reconnecting", "retrying", "waiting_for_tuner"].contains(state)
            && !cancellationRequested
    }
    var canDelete: Bool { ["failed", "cancelled", "expired", "partial"].contains(state) }

    var progress: Double {
        let total = end.timeIntervalSince(start)
        guard total > 0 else { return 0 }
        return min(1, max(0, Date().timeIntervalSince(start) / total))
    }
    var elapsed: String {
        guard let began = startedAt else { return "Sin datos todavía" }
        return Self.duration(max(0, Int(Date().timeIntervalSince(began))))
    }
    var remaining: String {
        Self.duration(max(0, Int(end.timeIntervalSinceNow)))
    }
    var received: String {
        ByteCountFormatter.string(fromByteCount: receivedBytes, countStyle: .file)
    }
    var statusLabel: String {
        if cancellationRequested && !isTerminal { return "Cancelación solicitada" }
        switch state {
        case "recording": return signalGrowing ? "Recibiendo datos" : "Grabando · comprobando señal"
        case "stopping": return "Deteniendo"
        case "reconnecting", "retrying": return "Reconectando"
        case "waiting_for_tuner": return "Esperando conexión libre"
        case "scheduled", "programada": return "Programada"
        case "finished", "completed": return "Finalizada"
        case "partial": return "Parcial · revisar"
        case "failed": return "Fallida"
        case "expired": return "Caducada"
        case "cancelled": return "Cancelada"
        default: return state
        }
    }
    private static func duration(_ n: Int) -> String {
        let h = n / 3600, m = (n % 3600) / 60, s = n % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%02d:%02d", m, s)
    }
}

@MainActor
final class SYNDVRMenuModel: ObservableObject {
    @Published private(set) var jobs: [MenuDVRJob] = []
    @Published private(set) var workerOnline = false
    @Published private(set) var occupied = 0
    @Published private(set) var capacity = 1
    @Published var message = ""

    private var timer: Timer?
    private let fm = FileManager.default
    private var lastBytes: [String: Int64] = [:]
    private var lastGrowth: [String: Date] = [:]
    private var pendingCancel: Set<String> = []

    private var root: URL {
        fm.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
    }
    private var jobsDir: URL { root.appendingPathComponent("jobs", isDirectory: true) }
    private var configURL: URL { root.appendingPathComponent("config.json") }

    var active: [MenuDVRJob] {
        jobs.filter { $0.isActive }
            .sorted { $0.start < $1.start }
    }
    var upcoming: [MenuDVRJob] {
        jobs.filter { ["scheduled", "programada"].contains($0.state) }
            .sorted { $0.start < $1.start }
    }
    var recent: [MenuDVRJob] {
        jobs.filter { $0.isTerminal }
            .sorted { ($0.finishedAt ?? $0.end) > ($1.finishedAt ?? $1.end) }
    }
    var isRecording: Bool { workerOnline && jobs.contains { $0.state == "recording" } }
    var isReconnecting: Bool {
        workerOnline && jobs.contains { ["retrying", "reconnecting", "waiting_for_tuner"].contains($0.state) }
    }

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refresh() }
        }
    }

    private func read<T: Decodable>(_ url: URL, as type: T.Type) -> T? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
    func refresh() {
        let now = Date()
        if let heartbeat = read(root.appendingPathComponent("worker.heartbeat.json"), as: DVRHeartbeat.self) {
            let age = now.timeIntervalSince1970 - heartbeat.timestamp
            workerOnline = age >= -5 && age < 12 && heartbeat.pid > 1
        } else { workerOnline = false }
        if let pool = read(root.appendingPathComponent("pool.status.json"), as: DVRPoolStatus.self),
           abs(now.timeIntervalSince1970 - pool.timestamp) < 15 {
            occupied = max(0, pool.occupied)
            capacity = max(1, pool.maxConnections)
        } else {
            occupied = 0
            if let data = try? Data(contentsOf: configURL),
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let count = obj["maxConnections"] as? Int { capacity = max(1, min(8, count)) }
        }
        let files = (try? fm.contentsOfDirectory(at: jobsDir, includingPropertiesForKeys: nil)) ?? []
        var observed = Set<String>()
        let updated: [MenuDVRJob] = files.compactMap { file in
            guard file.pathExtension == "json",
                  let id = UUID(uuidString: file.deletingPathExtension().lastPathComponent)?.uuidString,
                  let job = read(file, as: DVRJobFile.self) else { return nil }
            let status = read(jobsDir.appendingPathComponent(id + ".status.json"), as: DVRStatusFile.self)
            let state = status?.state ?? "scheduled"
            let size = max(0, status?.receivedBytes ?? 0)
            if let previous = lastBytes[id], size > previous { lastGrowth[id] = now }
            if lastBytes[id] == nil && size > 0 { lastGrowth[id] = now }
            lastBytes[id] = size
            observed.insert(id)
            if ["cancelled", "failed", "finished", "partial", "expired", "completed"].contains(state) {
                pendingCancel.remove(id)
            }
            let growing = lastGrowth[id].map { now.timeIntervalSince($0) < 7 } ?? false
            return MenuDVRJob(
                id:id, channel:job.channel, title:job.title,
                start:Date(timeIntervalSince1970:job.start),
                end:Date(timeIntervalSince1970:job.end), folder:job.folder,
                state:state, startedAt:status?.startedAt.map(Date.init(timeIntervalSince1970:)),
                finishedAt:status?.finishedAt.map(Date.init(timeIntervalSince1970:)),
                updatedAt:status?.updatedAt.map(Date.init(timeIntervalSince1970:)),
                retryAt:status?.retryAt.map(Date.init(timeIntervalSince1970:)),
                receivedBytes:size, parts:status?.parts?.count ?? 0,
                error:status?.error, warning:status?.warning,
                outputPath:status?.outputPath,
                signalGrowing:growing,
                cancellationRequested:pendingCancel.contains(id)
            )
        }
        lastBytes = lastBytes.filter { observed.contains($0.key) }
        lastGrowth = lastGrowth.filter { observed.contains($0.key) }
        pendingCancel = pendingCancel.intersection(observed)
        jobs = updated
    }

    func cancel(_ job: MenuDVRJob) {
        guard job.canCancel, UUID(uuidString: job.id) != nil else { return }
        do {
            let path = jobsDir.appendingPathComponent(job.id + ".cancel")
            try Data().write(to: path, options: .atomic)
            try fm.setAttributes([.posixPermissions: NSNumber(value: 0o600)], ofItemAtPath: path.path)
            pendingCancel.insert(job.id)
            message = "Cancelación solicitada para \(job.channel). Se conserva lo grabado."
            refresh() // Does not claim that cancellation has finished.
        } catch {
            message = "No se pudo solicitar la cancelación: \(error.localizedDescription)"
        }
    }

    func delete(_ job: MenuDVRJob) {
        guard job.canDelete, UUID(uuidString:job.id) != nil else { return }
        do {
            for suffix in [".json", ".status.json", ".cancel"] {
                let path = jobsDir.appendingPathComponent(job.id + suffix)
                if fm.fileExists(atPath: path.path) { try fm.removeItem(at: path) }
            }
            message = "Tarea eliminada. Los vídeos se conservan."
            refresh()
        } catch { message = "No se pudo eliminar: \(error.localizedDescription)" }
    }

    // SYN_VER_EN_SYN_93: comunica solo la ruta del MKV final, nunca IPTV.
    func verEnSYN93(_ job: MenuDVRJob) {
        guard job.isTerminal, let path = job.outputPath,
              fm.fileExists(atPath: path),
              ["mkv", "mp4", "mov", "ts"].contains(URL(fileURLWithPath: path).pathExtension.lowercased()) else {
            message = "El vídeo no está disponible o todavía se está finalizando."
            return
        }
        var request = URLComponents()
        request.scheme = "synrec"
        request.host = "open"
        request.queryItems = [URLQueryItem(name: "path", value: path)]
        guard let url = request.url else { message = "No se pudo preparar la ruta del archivo."; return }
        NSWorkspace.shared.open(url)
    }

    func showFile(_ job: MenuDVRJob) {
        if let path = job.outputPath, fm.fileExists(atPath:path) {
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath:path)])
        } else if fm.fileExists(atPath:job.folder) {
            NSWorkspace.shared.open(URL(fileURLWithPath:job.folder, isDirectory:true))
        } else {
            message = "La carpeta de esta grabación no está disponible."
        }
    }
    func openRecordings() {
        let config = fm.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/SYN Native DVR/recording_folder.json")
        let fallback = fm.homeDirectoryForCurrentUser.appendingPathComponent("Movies/SYN Grabaciones").path
        var folder = fallback
        if let data = try? Data(contentsOf:config),
           let obj = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
           let configured = obj["folder"] as? String, configured.hasPrefix("/") { folder = configured }
        if let existing = jobs.first(where: { fm.fileExists(atPath:$0.folder) }) {
            folder = existing.folder
        }
        if fm.fileExists(atPath:folder) { NSWorkspace.shared.open(URL(fileURLWithPath:folder, isDirectory:true)) }
        else { message = "No encuentro la carpeta de grabaciones." }
    }
    func openSYN() {
        let app = URL(fileURLWithPath:"/Applications/SYN.app", isDirectory:true)
        if fm.fileExists(atPath:app.path) {
            NSWorkspace.shared.open(app)
        } else { message = "No encuentro SYN en /Applications." }
    }

    func saveCapacity(_ value: Int) {
        guard (1...8).contains(value) else { return }
        do {
            try fm.createDirectory(at:root, withIntermediateDirectories:true)
            let payload = try JSONSerialization.data(withJSONObject:["maxConnections":value])
            try payload.write(to:configURL, options:.atomic)
            try fm.setAttributes([.posixPermissions:NSNumber(value:0o600)], ofItemAtPath:configURL.path)
            capacity = value
            message = "Límite actualizado a \(value) conexión(es)."
        } catch { message = "No se pudo guardar el límite: \(error.localizedDescription)" }
    }
}
