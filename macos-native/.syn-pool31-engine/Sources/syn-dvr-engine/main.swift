import Foundation
import Dispatch
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

// SYN DVR Engine 2.0 beta 1: standalone, deliberately isolated from live SYN/VLC.
// Existing SYN JSON schema accepted; no URLs/credentials in status, logs or manifest.

let fm = FileManager.default
let env = ProcessInfo.processInfo.environment
let userHome = fm.homeDirectoryForCurrentUser
let root = URL(fileURLWithPath: env["SYN_DVR_V2_HOME"] ?? userHome.appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0").path, isDirectory: true)
let jobs = root.appendingPathComponent("jobs", isDirectory: true)
let logs = root.appendingPathComponent("engine.log")
let ffmpeg = env["SYN_DVR_V2_FFMPEG"] ?? ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"].first(where: { fm.isExecutableFile(atPath: $0) }) ?? ""
let remuxFFmpeg = env["SYN_DVR_V2_REMUX_FFMPEG"] ?? ffmpeg
let ffprobe = env["SYN_DVR_V2_FFPROBE"] ?? ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"].first(where: { fm.isExecutableFile(atPath: $0) }) ?? ""
let nowTime = { Date().timeIntervalSince1970 }

struct Job: Codable {
    var url: String
    var channel: String
    var title: String
    var namingVersion: Int?  // SYN_NAMES_92: optional for old job JSON
    var start: Double
    var end: Double
    var folder: String
}

struct Part: Codable {
    var file: String
    var startedAt: Double
    var finishedAt: Double?
    var bytes: Int64
    var exitCode: Int32?
}

struct Status: Codable {
    var state: String
    var startedAt: Double?
    var finishedAt: Double?
    var error: String?
    var ffmpegPID: Int?
    var retries: Int
    var retryAt: Double?
    var outputPath: String?
    var updatedAt: Double?
    var parts: [Part]
    var receivedBytes: Int64
    var warning: String?

    static func initial() -> Status {
        Status(state: "scheduled", startedAt: nil, finishedAt: nil, error: nil,
               ffmpegPID: nil, retries: 0, retryAt: nil, outputPath: nil,
               updatedAt: nil, parts: [], receivedBytes: 0, warning: nil)
    }
}

struct Heartbeat: Codable {
    let timestamp: Double
    let pid: Int32
    let version: String
}

func read<T: Decodable>(_ path: URL, as: T.Type) -> T? {
    guard let data = try? Data(contentsOf: path) else { return nil }
    return try? JSONDecoder().decode(T.self, from: data)
}

func write<T: Encodable>(_ value: T, to path: URL) {
    guard let data = try? JSONEncoder().encode(value) else { return }
    do {
        try data.write(to: path, options: .atomic)
        try fm.setAttributes([.posixPermissions: NSNumber(value: 0o600)], ofItemAtPath: path.path)
    } catch { fputs("Error guardando estado\n", stderr) }
}
func save(_ status: Status, id: String) {
    var s = status
    s.updatedAt = nowTime()
    write(s, to: jobs.appendingPathComponent("\(id).status.json"))
}
func log(_ message: String) {
    // Never log URLs, process arguments, HTTP headers or credentials.
    let line = "[\(Int(nowTime()))] " + message + "\n"
    guard let data = line.data(using: .utf8) else { return }
    if fm.fileExists(atPath: logs.path), let h = try? FileHandle(forWritingTo: logs) {
        h.seekToEndOfFile(); h.write(data); h.closeFile()
    } else { try? data.write(to: logs, options: .atomic) }
}
func mkdir(_ url: URL) throws {
    try fm.createDirectory(at: url, withIntermediateDirectories: true,
                           attributes: [.posixPermissions: NSNumber(value: 0o700)])
}
func bytes(_ path: String) -> Int64 {
    (try? fm.attributesOfItem(atPath: path)[.size] as? NSNumber)?.int64Value ?? 0
}
func safeName(_ input: String) -> String {
    let candidate = String(input.replacingOccurrences(of: #"[^\p{L}\p{N} ._-]"#, with: "_", options: .regularExpression).prefix(60))
    let stripped = candidate.trimmingCharacters(in: .whitespacesAndNewlines)
    return stripped.isEmpty ? "Grabación" : stripped
}
// SYN_NAMES_92 — file-safe form of user-visible title. No slashes (path separators)
// or colons; pre-existing jobs always retain their original ID-based path.
func recordingFileBase92(_ job: Job, id: String) -> String {
    guard job.namingVersion == 2 else { return "\(safeName(job.title))_\(id.prefix(8))" }
    let filesystemTitle = job.title.replacingOccurrences(of: "/", with: "-")
        .replacingOccurrences(of: ":", with: "-")
    let sanitized = String(filesystemTitle.replacingOccurrences(
        of: #"[^\p{L}\p{N} ._-]"#, with: "_", options: .regularExpression).prefix(140))
    let clean = sanitized.trimmingCharacters(in: .whitespacesAndNewlines)
    return clean.isEmpty ? "Grabación - \(id.prefix(8))" : clean
}
func isTerminal(_ state: String) -> Bool {
    ["finished", "failed", "cancelled", "partial", "expired"].contains(state)
}
func isValidJob(_ job: Job) -> Bool {
    guard let u = URL(string: job.url), ["http", "https"].contains(u.scheme?.lowercased() ?? "") else { return false }
    return job.end > job.start && job.end.isFinite && job.start.isFinite &&
           job.end - job.start <= 48 * 3600 && job.folder.hasPrefix("/")
}
func exec(_ path: String, _ arguments: [String], timeout: Double = 45) -> Bool {
    guard fm.isExecutableFile(atPath: path) else { return false }
    let p = Process(); p.executableURL = URL(fileURLWithPath: path); p.arguments = arguments
    p.standardInput = FileHandle.nullDevice
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { return false }
    let deadline = nowTime() + timeout
    while p.isRunning && nowTime() < deadline { Thread.sleep(forTimeInterval: 0.1) }
    if p.isRunning { p.terminate(); return false }
    return p.terminationStatus == 0
}

// SYN_DVR_CLEAN_311: only delete captured parts after verifying MKV packet retention.
// Never delete unknown, active, damaged, incomplete or unverified TS files.
struct VideoPacketCounts {
    var video: Int64 = 0
    var audio: Int64 = 0
}
func packetCounts(_ path: String) -> VideoPacketCounts? {
    guard fm.isExecutableFile(atPath: ffprobe) else { return nil }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: ffprobe)
    p.arguments = ["-v", "error", "-count_packets", "-show_entries",
                   "stream=codec_type,nb_read_packets", "-of", "json", path]
    let output = Pipe()
    p.standardInput = FileHandle.nullDevice
    p.standardOutput = output
    p.standardError = FileHandle.nullDevice
    do { try p.run() } catch { return nil }
    let deadline = nowTime() + 90
    while p.isRunning && nowTime() < deadline { Thread.sleep(forTimeInterval: 0.08) }
    if p.isRunning {
        p.terminate()
        let grace = nowTime() + 1
        while p.isRunning && nowTime() < grace { Thread.sleep(forTimeInterval: 0.05) }
        if p.isRunning { _ = kill(p.processIdentifier, SIGKILL) }
        return nil
    }
    guard p.terminationStatus == 0,
          let object = try? JSONSerialization.jsonObject(with: output.fileHandleForReading.readDataToEndOfFile()) as? [String: Any],
          let streams = object["streams"] as? [[String: Any]] else { return nil }
    var result = VideoPacketCounts()
    for stream in streams {
        guard let type = stream["codec_type"] as? String,
              let raw = stream["nb_read_packets"] as? String,
              let count = Int64(raw), count > 0 else { continue }
        if type == "video" { result.video += count }
        if type == "audio" { result.audio += count }
    }
    return result.video > 0 ? result : nil
}
func cleanupVerifiedParts(_ parts: [Part], final: URL, folder: URL, list: URL) {
    guard !parts.isEmpty, bytes(final.path) > 4096,
          final.deletingLastPathComponent().standardizedFileURL == folder.standardizedFileURL,
          let output = packetCounts(final.path) else { return }
    let expected = Set(parts.map { URL(fileURLWithPath: $0.file).standardizedFileURL.path })
    guard expected.count == parts.count else { return }
    let actual = (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
    // A crash can leave unregistered segments. Preserve everything in that case.
    let captured = Set(actual.filter {
        $0.lastPathComponent.range(of: #"^part_[0-9]{5}\.ts$"#, options: .regularExpression) != nil
    }.map { $0.standardizedFileURL.path })
    guard captured == expected else { return }
    var expectedCounts = VideoPacketCounts()
    for part in parts {
        let path = URL(fileURLWithPath: part.file).standardizedFileURL
        guard path.deletingLastPathComponent() == folder.standardizedFileURL,
              path.lastPathComponent.range(of: #"^part_[0-9]{5}\.ts$"#, options: .regularExpression) != nil,
              bytes(path.path) == part.bytes, part.bytes > 4096,
              let counts = packetCounts(path.path) else { return }
        expectedCounts.video += counts.video
        expectedCounts.audio += counts.audio
    }
    // A successful FFmpeg exit alone is not sufficient. Every video/audio stream
    // must retain virtually all packets in the completed container.
    guard output.video >= expectedCounts.video - max(2, expectedCounts.video / 100),
          expectedCounts.audio == 0 ||
          output.audio >= expectedCounts.audio - max(4, expectedCounts.audio / 100) else {
        log("CLEAN: MKV no conserva todos los paquetes esperados; TS protegidos")
        return
    }
    for part in parts {
        do { try fm.removeItem(atPath: part.file) }
        catch { log("CLEAN: no se pudo retirar una parte; resto conservado"); return }
    }
    try? fm.removeItem(at: list)
    log("CLEAN: MKV verificado, \(parts.count) TS temporales retirados")
}

// Remux only after the capture is over. Preserve originals unless MKV passes verification.
// A multiple-part capture is ALWAYS labelled partial (gaps/overlap unverified).
func finalize(id: String, job: Job, previous: Status, at: Double, cancelled: Bool) -> Status {
    var s = previous
    s.ffmpegPID = nil; s.retryAt = nil; s.finishedAt = at
    s.receivedBytes = s.parts.reduce(0) { $0 + $1.bytes }
    let parts = s.parts.filter { $0.bytes > 4096 && fm.fileExists(atPath: $0.file) }
    let jobFolder = URL(fileURLWithPath: job.folder, isDirectory: true)
        .appendingPathComponent("SYN-DVR2_\(id)", isDirectory: true)
    if parts.isEmpty {
        s.state = cancelled ? "cancelled" : "failed"
        s.error = cancelled ? nil : "No se recibieron datos de vídeo"
        save(s, id: id)
        return s
    }
    s.outputPath = parts[0].file
    if cancelled { s.state = "cancelled" }
    else if parts.count > 1 || s.warning != nil {
        s.state = "partial"
        s.warning = "\(parts.count) tramo(s): recepción interrumpida o discontinuidad posible; revisar"
    } else { s.state = "finished" }
    let list = jobFolder.appendingPathComponent("concat.ffconcat")
    let listText = "ffconcat version 1.0\n" + parts.map { part in
        "file '" + part.file.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }.joined(separator: "\n") + "\n"
    try? listText.write(to: list, atomically: true, encoding: .utf8)
    let final = jobFolder.appendingPathComponent("\(recordingFileBase92(job, id: id)).mkv")
    if fm.isExecutableFile(atPath: remuxFFmpeg) &&
        exec(remuxFFmpeg, ["-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                      "-fflags", "+genpts", "-f", "concat", "-safe", "0", "-i", list.path,
                      "-map", "0:v?", "-map", "0:a?", "-c", "copy", "-avoid_negative_ts", "make_zero", final.path], timeout: 150) && bytes(final.path) > 4096 {
        s.outputPath = final.path
    } else {
        s.state = cancelled ? "cancelled" : "partial"
        s.warning = "Se conservan los tramos TS; no se pudo crear un MKV verificable"
    }
    // Never claim perfect continuity after a reconnect, even if remux succeeds.
    let manifest = jobFolder.appendingPathComponent("capture-manifest.json")
    save(s, id: id)
    write(s, to: manifest)
    // A partial/cancelled capture may still be a valid playable MKV.
    // Keep originals if ffprobe or packet-retention verification fails.
    if s.outputPath == final.path {
        cleanupVerifiedParts(parts, final: final, folder: jobFolder, list: list)
    }
    return s
}

final class Capture {
    let process: Process
    var pid: pid_t = 0
    let input: Pipe
    let partPath: String
    let startedAt: Double
    let job: Job
    var stoppingAt: Double?
    var sentTerm = false
    var sentKill = false
    var previousSize: Int64 = 0
    var lastGrowthAt: Double
    private let stateLock = NSLock()
    private var completedCode: Int32?

    func completed(_ p: Process) {
        stateLock.lock(); completedCode = p.terminationStatus; stateLock.unlock()
    }
    var exitCode: Int32? {
        stateLock.lock(); defer { stateLock.unlock() }
        return completedCode
    }

    init(process: Process, input: Pipe, partPath: String, startedAt: Double, job: Job) {
        self.process = process; self.input = input; self.partPath = partPath
        self.startedAt = startedAt; self.job = job
        self.lastGrowthAt = startedAt
    }
}


// SYN_DVR_POOL_3: one upstream process PER DISTINCT SOURCE, bounded by subscribed capacity.
// All consumers (viewing / recordings / scheduled jobs) share a loopback playlist.
// Source URLs never occur in logs or status snapshots; viewer.json and jobs are mode 0600.
func sourceKey(_ source: String) -> String {
    var h: UInt64 = 14695981039346656037
    for c in source.utf8 { h = (h ^ UInt64(c)) &* 1099511628211 }
    return String(format: "%016llx", h)
}
struct ViewerRequest: Codable {
    let url: String
    let pid: Int32
    let updatedAt: Double
}
struct PoolSessionStatus: Codable {
    let key: String
    let localURL: String
    let state: String
    let pid: Int32
    let recording: Bool
}
struct PoolStatus: Codable {
    let timestamp: Double
    var maxConnections: Int
    let occupied: Int
    let viewerAllowed: Bool
    let sessions: [PoolSessionStatus]
}
final class PoolSession {
    let url: String
    let key: String
    let folder: URL
    var process: Process?
    var state = "buffering"
    var startedAt = 0.0
    init(url: String, folder: URL) {
        self.url = url; self.key = sourceKey(url)
        self.folder = folder
    }
}
final class TunerPool {
    let base = root.appendingPathComponent("live", isDirectory: true)
    let portFile = root.appendingPathComponent("pool.port")
    let snapshot = root.appendingPathComponent("pool.status.json")
    let viewerFile = root.appendingPathComponent("viewer.json")
    var maxConnections: Int
    let python = env["SYN_DVR_POOL_PYTHON"] ?? ["/opt/homebrew/bin/python3","/usr/bin/python3","/usr/local/bin/python3"].first(where: { fm.isExecutableFile(atPath: $0) }) ?? ""
    let serverPath = env["SYN_DVR_POOL_SERVER"] ?? ""
    var server: Process?
    var port: Int?
    var sessions: [String: PoolSession] = [:]
    // Grace period for the provider-side TCP session to close before reusing capacity.
    var lastReleaseAt = -Double.infinity

    // SYN_POOL_31: capacity can change from MenuBar without restarting any recording.
    // SYN_DVR_RECORDER_UA43_ENGINE: apply only when opening a new provider connection.
    // Existing receiver processes keep the User-Agent with which they started.
    func configuredUserAgent43() -> String {
        let fallback = "VLC/3.0.21 LibVLC/3.0.21"
        let path = root.appendingPathComponent("recorder-user-agent.json")
        guard let data = try? Data(contentsOf: path),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let configured = value["userAgent"] as? String else { return fallback }
        // Never allow HTTP header injection; invalid config falls back to known-safe VLC.
        guard !configured.isEmpty && configured.utf8.count <= 512 &&
              !configured.unicodeScalars.contains(where: {
                let code = $0.value
                return code < 32 || code == 127
              }) else { return fallback }
        return configured
    }
    func configuredLimit() -> Int {
        let config = root.appendingPathComponent("config.json")
        if let content = try? Data(contentsOf: config),
           let object = try? JSONSerialization.jsonObject(with: content) as? [String: Any],
           let requested = object["maxConnections"] as? Int {
            return min(8, max(1, requested))
        }
        return min(8, max(1, Int(env["SYN_DVR_MAX_CONNECTIONS"] ?? "") ?? 1))
    }
    init() { maxConnections = 1; maxConnections = configuredLimit() }
    func begin() -> Bool {
        guard !python.isEmpty, !serverPath.isEmpty, fm.fileExists(atPath: serverPath) else {
            log("POOL: falta servidor HLS local"); return false
        }
        do { try mkdir(base) } catch { return false }
        try? fm.removeItem(at: portFile)
        let p = Process()
        p.executableURL = URL(fileURLWithPath: python)
        p.arguments = [serverPath, base.path, portFile.path]
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return false }
        server = p
        let deadline = nowTime()+6
        while nowTime() < deadline {
            if let data = try? String(contentsOf: portFile, encoding: .utf8),
               let n = Int(data.trimmingCharacters(in: .whitespacesAndNewlines)), n > 0 {
                port = n
                return true
            }
            if !p.isRunning { break }
            Thread.sleep(forTimeInterval: 0.08)
        }
        p.terminate()
        return false
    }
    func currentViewer(now: Double) -> String? {
        guard let viewer = read(viewerFile, as: ViewerRequest.self),
              viewer.updatedAt >= now - 5, viewer.updatedAt <= now + 3,
              viewer.pid > 1, kill(viewer.pid,0) == 0,
              let u = URL(string: viewer.url), ["http","https"].contains(u.scheme?.lowercased() ?? "")
        else { return nil }
        return viewer.url
    }
    func localURL(_ remote: String) -> String? {
        guard let port = port else { return nil }
        return "http://127.0.0.1:\(port)/\(sourceKey(remote))/live.m3u8"
    }
    func ready(_ remote: String) -> Bool {
        let key = sourceKey(remote)
        guard let session = sessions[key], session.url == remote, session.process?.isRunning == true,
              let playlist = try? String(contentsOf: session.folder.appendingPathComponent("live.m3u8"), encoding: .utf8) else { return false }
        return playlist.contains(".ts")
    }
    func stop(_ key: String) {
        guard let session = sessions[key] else { return }
        if let p = session.process, p.isRunning {
            p.terminate()
            let timeout = nowTime()+1.5
            while p.isRunning && nowTime()<timeout { Thread.sleep(forTimeInterval: 0.03) }
            if p.isRunning { _ = kill(p.processIdentifier, SIGKILL) }
            let finalDeadline = nowTime()+1.0
            while p.isRunning && nowTime()<finalDeadline { Thread.sleep(forTimeInterval: 0.03) }
            // Never start a replacement on a slot that could still be consuming
            // the provider subscription. The next tick will retry cleanup.
            if p.isRunning && !(kill(p.processIdentifier, 0) == -1 && errno == ESRCH) {
                log("POOL: receptor aún activo, esperando liberación segura")
                return
            }
        }
        sessions.removeValue(forKey: key)
        lastReleaseAt = nowTime()
        try? fm.removeItem(at: session.folder)
        log("POOL: receptor liberado")
    }
    func start(_ remote: String) {
        guard fm.isExecutableFile(atPath: ffmpeg) else { log("POOL: FFmpeg no disponible"); return }
        let key = sourceKey(remote)
        let dir = base.appendingPathComponent(key, isDirectory: true)
        do { try mkdir(dir) } catch { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: ffmpeg)
        p.arguments = ["-nostdin","-hide_banner","-loglevel","error","-nostats",
                       "-user_agent",configuredUserAgent43(), "-i", remote,
                       "-map","0:v?","-map","0:a?","-c","copy",
                       "-f","hls","-hls_time","2","-hls_list_size","180",
                       "-hls_start_number_source","epoch_us",
                       "-hls_flags","delete_segments+append_list+omit_endlist+program_date_time+discont_start",
                       "-hls_segment_filename",dir.appendingPathComponent("segment_%020d.ts").path,
                       dir.appendingPathComponent("live.m3u8").path]
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do {
            try p.run()
            let session = PoolSession(url: remote, folder: dir)
            session.process = p; session.startedAt = nowTime()
            sessions[key] = session
            log("POOL: receptor iniciado; sesiones=\(sessions.count)/\(maxConnections)")
        } catch { log("POOL: fallo al iniciar receptor") }
    }
    func refresh(recordingSources: [String], viewer: String?, now: Double) {
        maxConnections = configuredLimit()
        if server?.isRunning != true {
            log("POOL: servidor local finalizado; no se abrirán nuevas sesiones")
            for key in Array(sessions.keys) { stop(key) }
            return
        }
        // Recording leases have strict priority; never preempt a recording for a viewer.
        let prioritized = Array(NSOrderedSet(array: recordingSources)) as? [String] ?? recordingSources
        let reserved = Array(prioritized.prefix(maxConnections))
        var desired = reserved
        if let viewer, !desired.contains(viewer), desired.count < maxConnections { desired.append(viewer) }
        let desiredKeys = Set(desired.map(sourceKey))
        for key in Array(sessions.keys) where !desiredKeys.contains(key) { stop(key) }
        for url in desired {
            let key = sourceKey(url)
            if let session = sessions[key], session.url != url { stop(key) }
            if let old = sessions[key], old.process?.isRunning != true { stop(key) }
            // After a process exits, the remote IPTV server may still count its
            // previous TCP stream. Do not establish a replacement immediately.
            if sessions[key] == nil && sessions.count < maxConnections &&
               now - lastReleaseAt >= 3.0 { start(url) }
        }
        var output: [PoolSessionStatus] = []
        for url in desired {
            guard let session = sessions[sourceKey(url)], session.url == url,
                  let local = localURL(url), let process = session.process, process.isRunning else { continue }
            let alive = ready(url)
            session.state = alive ? "receiving" : "buffering"
            output.append(PoolSessionStatus(key:session.key,localURL:local,
                                            state:session.state,pid:process.processIdentifier,
                                            recording:reserved.contains(url)))
        }
        write(PoolStatus(timestamp:now,maxConnections:maxConnections,
                         occupied:output.count,viewerAllowed:viewer == nil || desired.contains(viewer!),
                         sessions:output), to:snapshot)
    }
    deinit {
        for key in Array(sessions.keys) { stop(key) }
        if let p = server, p.isRunning {
            p.terminate()
            let deadline = nowTime() + 1.5
            while p.isRunning && nowTime() < deadline { Thread.sleep(forTimeInterval: 0.05) }
            if p.isRunning { _ = kill(p.processIdentifier, SIGKILL) }
        }
    }
}

final class Engine {
    var active: [String: Capture] = [:]
    let poll: Double = 1.0
    let pool = TunerPool()
    private let signalLock = NSLock()
    private var shutdownRequested = false
    private func requestShutdown() {
        signalLock.lock(); shutdownRequested = true; signalLock.unlock()
    }
    private func shouldShutdown() -> Bool {
        signalLock.lock(); defer { signalLock.unlock() }
        return shutdownRequested
    }

    func update(_ id: String, _ job: Job, _ c: Capture, _ s: inout Status, _ now: Double) {
        let size = bytes(c.partPath)
        if size > c.previousSize { c.previousSize = size; c.lastGrowthAt = now }
        // POSIX liveness is checked independently from Foundation's terminationHandler.
        // On some Swift runtimes, the callback can arrive late after a signalled
        // ffmpeg has already exited; never leave the task stuck in "stopping".
        let pid = c.pid
        let processGone = kill(pid, 0) == -1 && errno == ESRCH
        if c.exitCode == nil && !processGone {
            let cancel = fm.fileExists(atPath: jobs.appendingPathComponent("\(id).cancel").path)
            if (cancel || now >= job.end || now - c.lastGrowthAt > 28) && c.stoppingAt == nil {
                c.stoppingAt = now
                let reason = cancel ? "cancelación" : now >= job.end ? "fin previsto" : "sin datos nuevos"
                log("\(id.prefix(8)): deteniendo por \(reason)")
                // SIGINT can be intercepted/ignored by ffmpeg wrappers.
                // SIGTERM is deterministic for cancellation and is escalated below.
                _ = kill(c.pid, SIGTERM)
                s.state = cancel || now >= job.end ? "stopping" : "reconnecting"
            }
            if let since = c.stoppingAt {
                if now - since > 2 && !c.sentTerm {
                    c.sentTerm = true; _ = kill(c.pid, SIGTERM)
                }
                if now - since > 4 && !c.sentKill {
                    c.sentKill = true; _ = kill(c.pid, SIGKILL)
                }
            }
            s.receivedBytes = s.parts.reduce(0) { $0 + $1.bytes } + size
            s.ffmpegPID = Int(c.pid)
            save(s, id: id)
            return
        }
        // The child may be gone before Foundation invokes terminationHandler.
        // Do not wait synchronously here: task status must remain responsive.
        c.input.fileHandleForWriting.closeFile()
        let code = c.exitCode ?? (c.stoppingAt == nil ? -1 : -15)
        let part = Part(file: c.partPath, startedAt: c.startedAt, finishedAt: now,
                        bytes: size, exitCode: code)
        s.parts.append(part)
        s.receivedBytes = s.parts.reduce(0) { $0 + $1.bytes }
        s.ffmpegPID = nil
        active.removeValue(forKey: id)
        let cancelled = fm.fileExists(atPath: jobs.appendingPathComponent("\(id).cancel").path)
        if now >= job.end - 1 || cancelled {
            let final = finalize(id: id, job: job, previous: s, at: now, cancelled: cancelled)
            log("\(id.prefix(8)): cierre \(final.state); tramos=\(s.parts.count)")
            return
        }
        // EOF code 0 before scheduled end is NOT successful completion.
        // If received data, the next attempt starts another immutable part.
        let noData = size < 4096
        if noData {
            s.retries += 1
        } else {
            s.retries = 0 // count consecutive no-data failures, not reconnect events
        }
        if s.retries >= 8 {
            // Data already captured remains accessible even if the source is lost.
            if s.parts.contains(where: { $0.bytes > 4096 }) {
                s.warning = "Agotados los reintentos; se conservan los tramos disponibles"
                _ = finalize(id: id, job: job, previous: s, at: now, cancelled: false)
            } else {
                s.state = "failed"; s.finishedAt = now
                s.error = "Ocho intentos consecutivos sin datos"
                save(s, id: id)
            }
            log("\(id.prefix(8)): sin datos, agotados reintentos")
            return
        }
        s.state = "retrying"
        s.warning = "La señal se interrumpió antes de la hora prevista"
        s.error = noData ? "Se interrumpió la recepción; reintentando" : nil
        let delay = noData ? min(30, Double(2 << min(5, s.retries))) : 2.0
        s.retryAt = now + delay
        save(s, id: id)
        log("\(id.prefix(8)): EOF código \(code); datos=\(size); reintento")
    }

    func start(id: String, job: Job, current: Status, now: Double) {
        guard fm.isExecutableFile(atPath: ffmpeg) else {
            var s = current; s.state = "failed"; s.error = "FFmpeg no disponible"; s.finishedAt = now
            save(s, id: id); return
        }
        let container = URL(fileURLWithPath: job.folder, isDirectory: true)
            .appendingPathComponent("SYN-DVR2_\(id)", isDirectory: true)
        do { try mkdir(container) } catch {
            var s = current; s.state = "failed"; s.error = "Carpeta de grabación inaccesible"
            save(s, id: id); return
        }
        let index = current.parts.count + 1
        let part = container.appendingPathComponent(String(format: "part_%05d.ts", index))
        // Never overwrite an earlier part, even after a crash/restart.
        if fm.fileExists(atPath: part.path) {
            var s = current; s.state = "failed"; s.error = "Parte existente sin registrar; se conserva para revisión"
            save(s, id: id); return
        }
        let p = Process(); p.executableURL = URL(fileURLWithPath: ffmpeg)
        // Recording FFmpeg reads loopback ONLY. Upstream connections belong to the pool.
        guard pool.ready(job.url), let local = pool.localURL(job.url) else {
            var s = current; s.state = "waiting_for_tuner"; s.retryAt = now + 1
            save(s, id: id); return
        }
        p.arguments = ["-nostdin", "-hide_banner", "-loglevel", "error", "-nostats",
                       "-rw_timeout", "12000000", "-live_start_index", "-1",
                       "-i", local,
                       "-t", String(max(1, Int(ceil(job.end - now)))),
                       "-map", "0:v?", "-map", "0:a?", "-c", "copy", "-f", "mpegts", part.path]
        let input = Pipe(); p.standardInput = input
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do {
            let c = Capture(process: p, input: input, partPath: part.path, startedAt: now, job: job)
            p.terminationHandler = { [weak c] ended in c?.completed(ended) }
            try p.run()
            c.pid = p.processIdentifier
            active[id] = c
            var s = current
            s.state = "recording"; s.startedAt = s.startedAt ?? now
            if s.parts.isEmpty { s.warning = nil }
            s.retryAt = nil; s.error = nil; s.ffmpegPID = Int(p.processIdentifier)
            save(s, id: id)
            log("\(id.prefix(8)): tramo \(index) iniciado")
        } catch {
            input.fileHandleForWriting.closeFile()
            var s = current; s.state = "retrying"; s.error = "No se pudo iniciar FFmpeg"
            s.retries += 1; s.retryAt = now + 10
            save(s, id: id)
        }
    }

    func tick() {
        let now = nowTime()
        write(Heartbeat(timestamp: now, pid: getpid(), version: "3.1-pool"), to: root.appendingPathComponent("worker.heartbeat.json"))
        // Collect ALL due recording leases before starting any job. Do not use
        // a second upstream when several consumers need exactly the same source.
        let candidates = (try? fm.contentsOfDirectory(at: jobs, includingPropertiesForKeys: nil)) ?? []
        let due: [(String, Job)] = candidates.compactMap { file in
            guard file.pathExtension == "json", !file.lastPathComponent.hasSuffix(".status.json"),
                  let id = UUID(uuidString: file.deletingPathExtension().lastPathComponent),
                  let job = read(file, as: Job.self), isValidJob(job),
                  job.start <= now, job.end > now,
                  let s = read(jobs.appendingPathComponent("\(id.uuidString).status.json"), as: Status.self),
                  !isTerminal(s.state),
                  !fm.fileExists(atPath: jobs.appendingPathComponent("\(id.uuidString).cancel").path)
            else { return nil }
            return (id.uuidString, job)
        }.sorted { $0.1.start < $1.1.start }
        pool.refresh(recordingSources: due.map { $0.1.url }, viewer: pool.currentViewer(now: now), now: now)
        for (id, capture) in active {
            let jobURL = jobs.appendingPathComponent("\(id).json")
            // Current in-memory capture remains owned, even if a UI removes the job file.
            guard let job = read(jobURL, as: Job.self) else { continue }
            var current = read(jobs.appendingPathComponent("\(id).status.json"), as: Status.self) ?? .initial()
            update(id, job, capture, &current, now)
        }
        let entries = (try? fm.contentsOfDirectory(at: jobs, includingPropertiesForKeys: nil)) ?? []
        for file in entries where file.pathExtension == "json" && !file.lastPathComponent.hasSuffix(".status.json") {
            let id = file.deletingPathExtension().lastPathComponent
            guard UUID(uuidString: id) != nil, active[id] == nil,
                  let job = read(file, as: Job.self) else { continue }
            var s = read(jobs.appendingPathComponent("\(id).status.json"), as: Status.self) ?? .initial()
            if isTerminal(s.state) { continue }
            if fm.fileExists(atPath: jobs.appendingPathComponent("\(id).cancel").path) {
                _ = finalize(id: id, job: job, previous: s, at: now, cancelled: true)
                continue
            }
            if s.state == "recording" || s.state == "stopping" || s.state == "reconnecting" {
                // Detect lost worker; DO NOT silently launch a competing capture.
                if let oldPid = s.ffmpegPID, kill(pid_t(oldPid), 0) == 0 {
                    continue
                }
                // A crash may leave part_N.ts not in manifest. Never overwrite it.
                let container = URL(fileURLWithPath: job.folder, isDirectory: true).appendingPathComponent("SYN-DVR2_\(id)")
                let next = container.appendingPathComponent(String(format: "part_%05d.ts", s.parts.count + 1))
                if fm.fileExists(atPath: next.path) {
                    let size = bytes(next.path)
                    s.parts.append(Part(file: next.path, startedAt: s.updatedAt ?? now, finishedAt: now, bytes: size, exitCode: nil))
                    s.warning = "Motor reiniciado durante la recepción; revisar posible discontinuidad"
                }
                s.ffmpegPID = nil; s.state = "retrying"; s.retryAt = now + 2
                save(s, id: id)
                continue
            }
            if now < job.start { continue }
            if now >= job.end {
                if s.parts.isEmpty {
                    s.state = "expired"; s.finishedAt = now; save(s, id: id)
                } else { _ = finalize(id: id, job: job, previous: s, at: now, cancelled: false) }
                continue
            }
            if let retryAt = s.retryAt, now < retryAt { continue }
            if !pool.ready(job.url) {
                s.state = "waiting_for_tuner"; s.warning = "Sin sintonizador disponible o señal local en preparación"
                s.retryAt = now + 2; save(s, id: id)
                continue
            }
            if !isValidJob(job) {
                s.state = "failed"; s.finishedAt = now; s.error = "Programación inválida"
                save(s, id: id); continue
            }
            start(id: id, job: job, current: s, now: now)
        }
    }

    func serve() {
        do { try mkdir(root); try mkdir(jobs) } catch {
            fputs("No se pueden crear las carpetas DVR 2.0\n", stderr); return
        }
        let lockPath = root.appendingPathComponent("engine.instance.lock").path
        let fd = open(lockPath, O_CREAT | O_RDWR | O_CLOEXEC, mode_t(0o600))
        guard fd >= 0 else { return }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else {
            log("Segunda instancia rechazada")
            close(fd); return
        }
        defer { _ = flock(fd, LOCK_UN); close(fd) }
        guard pool.begin() else { log("POOL: servidor HLS no iniciado"); return }
        // launchctl bootout sends SIGTERM. Always release the provider sessions
        // before the worker exits; otherwise the old HTTP streams may survive.
        _ = signal(SIGTERM, SIG_IGN)
        _ = signal(SIGINT, SIG_IGN)
        let termSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .global())
        let intSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .global())
        termSource.setEventHandler { [weak self] in self?.requestShutdown() }
        intSource.setEventHandler { [weak self] in self?.requestShutdown() }
        termSource.resume(); intSource.resume()
        log("Motor 3.1 pool iniciado; conexiones máximas=\(pool.maxConnections)")
        while !shouldShutdown() { tick(); Thread.sleep(forTimeInterval: poll) }
        termSource.cancel(); intSource.cancel()
        for (_, capture) in active where capture.process.isRunning { capture.process.terminate() }
        log("POOL: cierre ordenado solicitado")
    }
}

func usage() {
    print("SYN DVR Pool 3.1 | serve | submit <job.json> | list | cleanup-completed | cancel <id> | delete <id>")
}

func main() {
    let args = CommandLine.arguments.dropFirst()
    guard let cmd = args.first else { usage(); return }
    if cmd == "serve" { let worker = Engine(); worker.serve(); return }
    do { try mkdir(root); try mkdir(jobs) } catch { fputs("Carpetas inaccesibles\n", stderr); return }
    switch cmd {
    case "submit":
        guard args.count == 2, let input = args.dropFirst().first,
              let job = read(URL(fileURLWithPath: input), as: Job.self), isValidJob(job) else {
            fputs("JSON de trabajo inválido; se requiere URL HTTP(S), título, fechas y carpeta\n", stderr)
            return
        }
        let id = UUID().uuidString
        write(job, to: jobs.appendingPathComponent("\(id).json"))
        save(.initial(), id: id)
        print("Tarea registrada: \(id) (motor 2.0)")
    case "cleanup-completed":
        // Idempotent maintenance for jobs finalized by earlier versions.
        // Never inspect or remove fragments from active/retrying jobs.
        let entries = (try? fm.contentsOfDirectory(at: jobs, includingPropertiesForKeys: nil)) ?? []
        var checked = 0
        for path in entries where path.pathExtension == "json" && !path.lastPathComponent.hasSuffix(".status.json") {
            let id = path.deletingPathExtension().lastPathComponent
            guard UUID(uuidString: id) != nil,
                  let job = read(path, as: Job.self),
                  let status = read(jobs.appendingPathComponent("\(id).status.json"), as: Status.self),
                  ["finished", "partial", "cancelled"].contains(status.state),
                  let output = status.outputPath, output.hasSuffix(".mkv"),
                  status.ffmpegPID == nil,
                  !status.parts.isEmpty else { continue }
            let folder = URL(fileURLWithPath: job.folder, isDirectory: true)
                .appendingPathComponent("SYN-DVR2_\(id)", isDirectory: true)
            let expected = folder.appendingPathComponent("\(recordingFileBase92(job, id: id)).mkv")
            guard URL(fileURLWithPath: output).standardizedFileURL == expected.standardizedFileURL else { continue }
            checked += 1
            cleanupVerifiedParts(status.parts,
                                 final: expected, folder: folder,
                                 list: folder.appendingPathComponent("concat.ffconcat"))
        }
        print("Limpieza revisada en \(checked) tarea(s). Los TS no verificables se conservan.")
    case "list":
        let entries = (try? fm.contentsOfDirectory(at: jobs, includingPropertiesForKeys: nil)) ?? []
        for path in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) where
            path.pathExtension == "json" && !path.lastPathComponent.hasSuffix(".status.json") {
            let id = path.deletingPathExtension().lastPathComponent
            guard UUID(uuidString: id) != nil else { continue }
            let s = read(jobs.appendingPathComponent("\(id).status.json"), as: Status.self)
            // Do not print URL, usernames, token or provider details.
            print("\(id) | \(s?.state ?? "scheduled") | \(s?.receivedBytes ?? 0) bytes | \(s?.parts.count ?? 0) tramo(s)")
        }
    case "cancel", "delete":
        guard args.count == 2, let id = args.dropFirst().first, UUID(uuidString: id) != nil else {
            fputs("ID UUID inválido\n", stderr); return
        }
        let task = jobs.appendingPathComponent("\(id).json")
        guard fm.fileExists(atPath: task.path) else { fputs("Trabajo no encontrado\n", stderr); return }
        if cmd == "cancel" {
            write(["cancel": true], to: jobs.appendingPathComponent("\(id).cancel"))
            print("Cancelación solicitada")
        } else {
            let s = read(jobs.appendingPathComponent("\(id).status.json"), as: Status.self)
            guard let status = s, isTerminal(status.state) else {
                fputs("Solo se pueden eliminar tareas terminadas; use cancel primero\n", stderr); return
            }
            // Preserve source recordings. No file in the recording folder is removed.
            try? fm.removeItem(at: task)
            try? fm.removeItem(at: jobs.appendingPathComponent("\(id).status.json"))
            try? fm.removeItem(at: jobs.appendingPathComponent("\(id).cancel"))
            print("Tarea eliminada; vídeo conservado")
        }
    default: usage()
    }
}
main()
