import AppKit
import Foundation
import SwiftUI

private struct MenuJobJSON: Decodable {
    let channel: String
    let title: String
    let start: Double
    let end: Double
    let folder: String
}

private struct MenuStatusJSON: Decodable {
    let state: String
    let startedAt: Double?
    let finishedAt: Double?
    let error: String?
    let outputPath: String?
}

private struct MenuHeartbeat: Decodable {
    let timestamp: Double
    let pid: Int32
}

struct MenuDVRJob: Identifiable {
    let id: String
    let channel: String
    let title: String
    let start: Date
    let end: Date
    let folder: String
    let state: String
    let error: String?
    let outputPath: String?
    let finishedAt: Date?

    var progress: Double {
        let span = end.timeIntervalSince(start)
        guard span > 0 else { return 0 }
        return min(1, max(0, Date().timeIntervalSince(start) / span))
    }

    var remaining: String {
        let seconds = max(0, Int(end.timeIntervalSinceNow))
        return "\(seconds / 3600)h \((seconds % 3600) / 60)m"
    }

    var statusLabel: String {
        switch state {
        case "finished", "completed": return "Terminada"
        case "partial": return "Parcial · revisar"
        case "reconnecting": return "Reconectando"
        case "failed": return "Fallida"
        case "expired": return "Caducada"
        case "cancelled": return "Cancelada"
        case "stopping": return "Deteniendo"
        case "retrying": return "Reintentando"
        default: return state
        }
    }
}

@MainActor
final class SYNDVRMenuModel: ObservableObject {
    @Published private(set) var jobs: [MenuDVRJob] = []
    @Published private(set) var workerOnline = false
    @Published var message = ""
    private var timer: Timer?

    private let fm = FileManager.default
    private var jobsDir: URL {
        fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/jobs", isDirectory: true)
    }

    var active: [MenuDVRJob] {
        jobs.filter { ["recording", "stopping", "reconnecting"].contains($0.state) }
    }
    var upcoming: [MenuDVRJob] {
        jobs.filter { ["scheduled", "programada", "retrying"].contains($0.state) }
            .sorted { $0.start < $1.start }
    }
    var recent: [MenuDVRJob] {
        jobs.filter { ["finished", "failed", "expired", "cancelled", "completed", "partial"].contains($0.state) }
            .sorted { ($0.finishedAt ?? $0.end) > ($1.finishedAt ?? $1.end) }
    }
    var isRecording: Bool { workerOnline && jobs.contains { $0.state == "recording" } }
    var isReconnecting: Bool { workerOnline && jobs.contains { ["retrying", "reconnecting"].contains($0.state) } }

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refresh() }
        }
    }

    func refresh() {
        let heartbeat = jobsDir.deletingLastPathComponent().appendingPathComponent("worker.heartbeat.json")
        let pulse = read(heartbeat, as: MenuHeartbeat.self)
        workerOnline = pulse.map { Date().timeIntervalSince1970 - $0.timestamp < 12 && $0.timestamp < Date().timeIntervalSince1970 + 8 } ?? false
        let files = (try? fm.contentsOfDirectory(at: jobsDir, includingPropertiesForKeys: nil, options: [])) ?? []
        jobs = files.compactMap { file -> MenuDVRJob? in
            guard file.pathExtension == "json", UUID(uuidString: file.deletingPathExtension().lastPathComponent) != nil else {
                return nil
            }
            guard let job = read(file, as: MenuJobJSON.self) else { return nil }
            let id = file.deletingPathExtension().lastPathComponent
            let status = read(jobsDir.appendingPathComponent(id + ".status.json"), as: MenuStatusJSON.self)
            return MenuDVRJob(id: id, channel: job.channel, title: job.title,
                              start: Date(timeIntervalSince1970: job.start), end: Date(timeIntervalSince1970: job.end),
                              folder: job.folder, state: status?.state ?? "scheduled",
                              error: status?.error, outputPath: status?.outputPath,
                              finishedAt: status?.finishedAt.map { Date(timeIntervalSince1970: $0) })
        }
    }

    private func read<T: Decodable>(_ url: URL, as type: T.Type) -> T? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }

    func cancel(_ job: MenuDVRJob) {
        guard UUID(uuidString: job.id) != nil else { return }
        do {
            let path = jobsDir.appendingPathComponent(job.id + ".cancel")
            try Data().write(to: path, options: .atomic)
            try fm.setAttributes([.posixPermissions: NSNumber(value: 0o600)], ofItemAtPath: path.path)
            message = "Detención solicitada: \(job.channel)"
        } catch {
            message = "No se pudo enviar la cancelación: \(error.localizedDescription)"
        }
    }

    func delete(_ job: MenuDVRJob) {
        guard UUID(uuidString: job.id) != nil,
              ["failed", "cancelled", "expired", "partial"].contains(job.state) else { return }
        do {
            for suffix in [".json", ".status.json", ".cancel"] {
                let file = jobsDir.appendingPathComponent(job.id + suffix)
                if fm.fileExists(atPath: file.path) { try fm.removeItem(at: file) }
            }
            message = "Tarea eliminada; los vídeos se conservan."
            refresh()
        } catch { message = "No se pudo eliminar la tarea: \(error.localizedDescription)" }
    }

    func showFile(_ job: MenuDVRJob) {
        if let output = job.outputPath, fm.fileExists(atPath: output) {
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: output)])
        } else {
            let folder = URL(fileURLWithPath: job.folder, isDirectory: true)
            if fm.fileExists(atPath: folder.path) {
                NSWorkspace.shared.open(folder)
            } else {
                message = "La carpeta de grabación no está disponible."
            }
        }
    }

    func openRecordings() {
        let root = fm.homeDirectoryForCurrentUser
        let config = root.appendingPathComponent("Library/Application Support/SYN Native DVR/recording_folder.json")
        var path = root.appendingPathComponent("Movies/SYN Grabaciones").path
        if let data = try? Data(contentsOf: config),
           let dict = (try? JSONSerialization.jsonObject(with: data)) as? [String: String],
           let specified = dict["folder"], specified.hasPrefix("/") {
            path = specified
        }
        let folder = URL(fileURLWithPath: path, isDirectory: true)
        if fm.fileExists(atPath: folder.path) {
            NSWorkspace.shared.open(folder)
        } else {
            message = "No existe todavía la carpeta de grabaciones."
        }
    }

    func openSYN() {
        if let app = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.mrseivane.SYNNativeAlpha") {
            NSWorkspace.shared.openApplication(at: app, configuration: NSWorkspace.OpenConfiguration()) { _, error in
                if let error {
                    Task { @MainActor in self.message = "No se pudo abrir SYN: \(error.localizedDescription)" }
                }
            }
        } else {
            message = "No se encuentra SYN instalado. Ábrelo desde tu compilación local."
        }
    }
}
