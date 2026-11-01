import Foundation
import SwiftUI
import AppKit

// SYN 7.0 — one upstream live connection per tuned channel.
// FFmpeg -> local HLS (rolling 6 minutes) -> VLC. Recording reads those exact local
// segments; never opens another upstream request for the same channel.
@MainActor
final class SYNSharedLive70 {
    static let shared = SYNSharedLive70()
    private var streams: [URL: Stream] = [:]
    private var viewerSource31: URL?
    private var viewerTimer31: Timer?
    private init() {}

    private func publishViewer31() {
        guard let source = viewerSource31 else { return }
        let root = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
        let path = root.appendingPathComponent("viewer.json")
        let payload: [String: Any] = ["url":source.absoluteString,
                                       "pid":ProcessInfo.processInfo.processIdentifier,
                                       "updatedAt":Date().timeIntervalSince1970]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }
        do {
            try data.write(to:path,options:.atomic)
            try FileManager.default.setAttributes([.posixPermissions: NSNumber(value: 0o600)],
                                                  ofItemAtPath:path.path)
        } catch { /* Fail closed: the pool will reject an unregistered viewer. */ }
    }
    private func tuneViewer31(_ url: URL) {
        viewerSource31 = url
        publishViewer31()
        if viewerTimer31 == nil {
            viewerTimer31 = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.publishViewer31() }
            }
        }
    }
    private func releaseViewer31() {
        viewerSource31 = nil
        viewerTimer31?.invalidate(); viewerTimer31 = nil
        let path = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/viewer.json")
        try? FileManager.default.removeItem(at:path)
    }

    private static func executable(_ possibilities: [String]) -> URL? {
        for candidate in possibilities where FileManager.default.isExecutableFile(atPath: candidate) {
            return URL(fileURLWithPath: candidate)
        }
        return nil
    }

    @MainActor
    final class Stream {
        let remote: URL
        let folder: URL
        let playlist: URL
        let local: URL
        // SYN_DVR_RECOVERY_801: conservar sesión HLS y archivo DVR al reabrir el origen.
        private var ffmpeg = Process()
        private let server = Process()
        private var ffmpegBinary: URL!
        private var ffmpegArguments: [String] = []
        private var recoveryTimer: Timer?
        private var nextRetryAt = Date.distantPast
        private var recoveryAttempts = 0
        private var lastFeedProgress = Date()
        private var lastPublishedSegment: String?
        private var shuttingDown = false
        private var writer: FileHandle?
        private var recordingTimer: Timer?
        private var seen: Set<String> = []
        private(set) var recordingURL: URL?
        private(set) var failed = false
        // SYN_71_RECORDING_HEALTH: detect a stalled feed and notify UI outside the DVR tab.
        private(set) var lastRecordingError: String?
        private var lastWrittenSegmentAt = Date()
        var isRecording: Bool { writer != nil }

        // SYN_POOL_31: the engine exclusively owns upstream FFmpeg and loopback HLS.
        // This viewer MUST NOT start its own HTTP connection or a second FFmpeg.
        private let pooled = true
        private let poolJoinedAt = Date().timeIntervalSince1970
        init?(remote: URL) {
            let base = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
            guard let raw = try? String(contentsOf: base.appendingPathComponent("pool.port"), encoding: .utf8),
                  let port = Int(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
                  (1...65535).contains(port) else { return nil }
            var hash: UInt64 = 14695981039346656037
            for b in remote.absoluteString.utf8 { hash = (hash ^ UInt64(b)) &* 1099511628211 }
            let key = String(format: "%016llx", hash)
            self.remote = remote
            folder = base.appendingPathComponent("live/" + key, isDirectory: true)
            playlist = folder.appendingPathComponent("live.m3u8")
            guard let loopback = URL(string: "http://127.0.0.1:\(port)/\(key)/live.m3u8") else { return nil }
            local = loopback
            // FFmpeg, HTTP server and all subscribers belong to the engine.
            // The stream wrapper only reads the engine's files. It never owns those processes.
        }

        private func monitorFeed801() { /* SYN_POOL_31: engine owns reconnection. */ }

        func waitUntilReady(_ completion: @escaping (Bool) -> Void) {
            var attempts = 0
            Timer.scheduledTimer(withTimeInterval: 0.35, repeats: true) { [weak self] timer in
                MainActor.assumeIsolated {
                    guard let self else { timer.invalidate(); completion(false); return }
                    attempts += 1
                    let text = try? String(contentsOf: self.playlist, encoding: .utf8)
                    if text?.contains(".ts") == true {
                        timer.invalidate()
                        completion(true)
                    } else if attempts >= 55 || self.viewerWasRejected31() {
                        timer.invalidate()
                        completion(false)
                    }
                }
            }
        }

        private func viewerWasRejected31() -> Bool {
            let path = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/pool.status.json")
            guard let data = try? Data(contentsOf: path),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let stamp = obj["timestamp"] as? Double, stamp >= poolJoinedAt,
                  let allowed = obj["viewerAllowed"] as? Bool else { return false }
            return !allowed
        }

        // Turn the currently buffered live segments into a seekable local VOD
        // snapshot. The upstream FFmpeg process continues receiving the SAME feed.
        func replaySnapshot() -> (url: URL, duration: TimeInterval)? {
            guard let raw = try? String(contentsOf: playlist, encoding: .utf8) else { return nil }
            let lines = raw.split(whereSeparator: \.isNewline).map(String.init)
            var pairs: [(Double, String)] = []
            var duration = 2.0
            for line in lines {
                if line.hasPrefix("#EXTINF:") {
                    let length = line.dropFirst("#EXTINF:".count).split(separator: ",").first ?? "2"
                    duration = Double(length) ?? 2.0
                } else if line.hasPrefix("segment_") && line.hasSuffix(".ts") {
                    pairs.append((duration, line))
                }
            }
            guard pairs.count >= 3 else { return nil }
            // Segment paths are unchanged; VLC only talks to the LOCAL HTTP server.
            let list = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:10", "#EXT-X-MEDIA-SEQUENCE:0"]
                + pairs.flatMap { ["#EXTINF:\($0.0),", $0.1] }
                + ["#EXT-X-ENDLIST"]
            let name = "replay_\(UUID().uuidString).m3u8"
            let output = folder.appendingPathComponent(name)
            do { try list.joined(separator: "\n").appending("\n").write(to: output, atomically: true, encoding: .utf8) }
            catch { return nil }
            return (local.deletingLastPathComponent().appendingPathComponent(name), pairs.reduce(0) { $0 + $1.0 })
        }

        private func publishedSegments() -> [String] {
            guard let txt = try? String(contentsOf: playlist, encoding: .utf8) else { return [] }
            return txt.split(whereSeparator: \.isNewline).map(String.init).filter {
                $0.hasPrefix("segment_") && $0.hasSuffix(".ts") && !$0.contains("/")
            }
        }

        func beginRecording() throws {
            throw NSError(domain: "SYNPOOL", code: 31,
                userInfo:[NSLocalizedDescriptionKey:"REC lo gestiona exclusivamente SYN DVR Engine 3.1"])
            // Legacy body is deliberately unreachable; removed in final migration.
            if isRecording { return }
            let fm = FileManager.default
            let location = SYNRecordingFolder75.current
            try fm.createDirectory(at: location, withIntermediateDirectories: true)
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd_HH-mm-ss"
            let path = location.appendingPathComponent("SYN_\(formatter.string(from: Date()))_\(UUID().uuidString.prefix(6)).ts")
            guard fm.createFile(atPath: path.path, contents: nil) else { throw NSError(domain: "SYNREC", code: 1) }
            writer = try FileHandle(forWritingTo: path)
            recordingURL = path
            lastRecordingError = nil
            lastWrittenSegmentAt = Date()
            // Ignore segments prior to pressing REC; begin with the next segment.
            seen = Set(publishedSegments())
            recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.65, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.flushRecording() }
            }
        }

        private func flushRecording() {
            guard let writer else { return }
            // Un microcorte no debe abortar ni cerrar el archivo DVR.
            // monitorFeed801() recupera el origen, y aquí se reanuda la escritura
            // de los segmentos completados en el MISMO archivo.
            if Date().timeIntervalSince(lastWrittenSegmentAt) > 90 {
                lastRecordingError = "Recepción interrumpida: intentando recuperar el canal"
            }
            for segment in publishedSegments() where !seen.contains(segment) {
                let path = folder.appendingPathComponent(segment)
                guard let bytes = try? Data(contentsOf: path) else { continue }
                do {
                    try writer.write(contentsOf: bytes)
                    seen.insert(segment)
                    lastWrittenSegmentAt = Date()
                } catch {
                    lastRecordingError = "Error escribiendo el archivo: " + error.localizedDescription
                    recordingTimer?.invalidate()
                    recordingTimer = nil
                    try? writer.close()
                    self.writer = nil
                    return
                }
            }
        }

        // SYN_REC_MANUAL_795: intentional stop is never a stream failure.
        func stopRecording() {
            flushPendingAndClose()
            lastRecordingError = nil
        }

        private func flushPendingAndClose() {
            recordingTimer?.invalidate()
            recordingTimer = nil
            if writer != nil { flushRecording() }
            try? writer?.close()
            writer = nil
        }

        func stop() {
            shuttingDown = true
            recoveryTimer?.invalidate()
            recoveryTimer = nil
            flushPendingAndClose()
            // SYN_POOL_31: no engine process is stopped by the viewer.
        }
        deinit {
            recoveryTimer?.invalidate()
            // SYN_POOL_31: no engine process is stopped by the viewer.
        }
    }

    func session(for url: URL, completion: @escaping (Stream?) -> Void) {
        tuneViewer31(url)
        if let existing = streams[url] {
            existing.waitUntilReady { ok in completion(ok ? existing : nil) }
            return
        }
        guard let stream = Stream(remote: url) else { completion(nil); return }
        streams[url] = stream
        stream.waitUntilReady { [weak self] ready in
            if !ready { self?.streams[url] = nil; stream.stop() }
            completion(ready ? stream : nil)
        }
    }

    func existing(for url: URL?) -> Stream? {
        guard let url else { return nil }
        return streams[url]
    }

    struct Recording: Identifiable {
        let id: String
        let source: URL
        let file: URL
    }
    func recordings() -> [Recording] {
        streams.compactMap { (url, stream) in
            guard stream.isRecording, let file = stream.recordingURL else { return nil }
            return Recording(id: url.absoluteString, source: url, file: file)
        }
    }
    func recordingIssues() -> [String] {
        streams.values.compactMap { $0.lastRecordingError }
    }
    func stopRecording(for source: URL, current: URL?) {
        streams[source]?.stopRecording()
        releaseUnrecorded(except: current)
    }
    func shutdown() {
        releaseViewer31()
        for stream in streams.values { stream.stop() }
        streams.removeAll()
    }
    func releaseUnrecorded(except current: URL?) {
        if current == nil { releaseViewer31() }
        let old = streams.filter { $0.key != current && !$0.value.isRecording }
        for (url, stream) in old {
            stream.stop()
            streams.removeValue(forKey: url)
        }
    }
}

struct SYNProgram70: Equatable {
    var title: String
    var start: Date?
    var end: Date?
}
struct SYNGuideChannel70: Identifiable, Equatable {
    var id: String
    var name: String
    var now: String
    var next: String
    var isFavorite: Bool
    var category: String = ""
    var logo: String = ""
    var fallbackLogo: String = ""
}
struct SYNGuideProgramme74: Identifiable, Equatable, Sendable {
    var title: String
    var start: Date
    var end: Date
    var id: String { "\(start.timeIntervalSince1970)|\(title)" }
}

// SYN 7.4 — Fullscreen EPG; same NSWindow as the active VLC canvas.
// Grid occupies the screen, but media/audio stays alive underneath it.
private struct SYNFullscreenMarginRequest90: Identifiable {
    let id = UUID()
    let channelID: String
    let title: String
    let start: Date
    let end: Date
}

struct SYNFullscreenGuide70: View {
    let channels: [SYNGuideChannel70]
    let tune: (String) -> Void
    let close: () -> Void
    let load: (String) async -> [SYNGuideProgramme74]
    let schedule: (String, String, Date, Date) throws -> Void
    @State private var pendingMargin90: SYNFullscreenMarginRequest90?
    @State private var query = ""
    @State private var favorites = false
    @State private var category = ""
    @State private var limit = 35
    @State private var hourOffset = 0
    @State private var fetched: [String: [SYNGuideProgramme74]] = [:]
    @State private var preparing77 = false
    // SYN_FULLSCREEN_GUIDE_84: el raton desplaza el NSScrollView horizontal real.
    private let slotWidth: CGFloat = 168
    private let channelWidth: CGFloat = 265
    private let rowHeight: CGFloat = 51
    private let totalSlots = 12

    private var categories: [String] {
        Array(Set(channels.map(\.category))).filter { !$0.isEmpty }.sorted()
    }
    private var filtered: [SYNGuideChannel70] {
        channels.filter { channel in
            (!favorites || channel.isFavorite) &&
            (category.isEmpty || channel.category == category) &&
            (query.isEmpty || channel.name.localizedStandardContains(query))
        }
    }
    // SYN_FULLSCREEN_GUIDE_82: mostrar todas las filas disponibles sin
    // recortarlas por un canal cuya EPG todavía no se ha descargado.
    private var shown: [SYNGuideChannel70] {
        Array(filtered.prefix(limit))
    }

    @MainActor private func preloadFullGuide77() async {
        let missing = Array(filtered.prefix(limit)).map(\.id).filter { fetched[$0] == nil }
        guard !missing.isEmpty else { return }
        preparing77 = true
        defer { preparing77 = false }
        for start in stride(from: 0, to: missing.count, by: 8) {
            if Task.isCancelled { return }
            let ids = Array(missing[start..<min(start + 8, missing.count)])
            let batch = await withTaskGroup(of: (String, [SYNGuideProgramme74]).self,
                                            returning: [(String, [SYNGuideProgramme74])].self) { group in
                for id in ids {
                    group.addTask { (id, await load(id)) }
                }
                var list: [(String, [SYNGuideProgramme74])] = []
                for await pair in group { list.append(pair) }
                return list
            }
            if Task.isCancelled { return }
            // Publicar inmediatamente cada lote: la tabla ya está completa
            // en canales y se rellenan las pastillas según llega la EPG.
            for (id, programmes) in batch { fetched[id] = programmes }
        }
    }
    private var origin: Date {
        let now = Date().addingTimeInterval(TimeInterval(hourOffset) * 3600)
        return Date(timeIntervalSince1970: floor(now.timeIntervalSince1970 / 1800) * 1800)
    }
    private func left(for date: Date) -> CGFloat {
        CGFloat(date.timeIntervalSince(origin) / 1800) * slotWidth
    }
    private func row(_ ch: SYNGuideChannel70, height: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            Color.white.opacity(0.035)
            let programs = fetched[ch.id] ?? []
            ForEach(programs.filter { $0.end > origin && $0.start < origin.addingTimeInterval(21600) }) { program in
                let x = max(0, left(for: program.start))
                let endX = min(CGFloat(totalSlots) * slotWidth, left(for: program.end))
                let width = max(0, endX - x - 2)
                if width > 2 {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(program.start, format: .dateTime.hour().minute()).font(.system(size: 9))
                        Text(program.title).font(.system(size: 11, weight: .semibold)).lineLimit(2)
                    }
                    .padding(6)
                    .frame(width: width, height: height - 3, alignment: .topLeading)
                    .background(Color(hue: Double(abs(ch.id.hashValue % 10)) / 10, saturation: 0.50, brightness: 0.60), in: RoundedRectangle(cornerRadius: 6))
                    .contextMenu {
                        Button("Programar grabación…") {
                            pendingMargin90 = SYNFullscreenMarginRequest90(channelID: ch.id,
                                title: program.title, start: program.start, end: program.end)
                        }
                    }
                    .offset(x: x, y: 1)
                }
            }
            if fetched[ch.id] == nil {
                Text("Cargando programación…")
                    .foregroundStyle(.white.opacity(0.53)).font(.caption)
                    .padding(.leading, 10).frame(height: height)
            } else if programs.isEmpty {
                Text("Sin programación disponible")
                    .foregroundStyle(.white.opacity(0.53)).font(.caption)
                    .padding(.leading, 10).frame(height: height)
            }
        }
        .frame(width: slotWidth * CGFloat(totalSlots), height: height)
        .clipped()

    }
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 15) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Guía de televisión").font(.title2.bold())
                    Text("EPG Xtream · reproducción y audio continúan en segundo plano")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                TextField("Buscar canal…", text: $query).frame(width: 200)
                    .textFieldStyle(.roundedBorder)
                Button { hourOffset -= 1 } label: { Image(systemName: "chevron.left") }
                Button("Ahora") { hourOffset = 0 }
                Button { hourOffset += 1 } label: { Image(systemName: "chevron.right") }
                Button(action: close) { Image(systemName: "xmark") }
                    .help("Cerrar guía · Esc")
            }
            .padding(18)
            Divider()
            HStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 8) {
                    Button("Todas las categorías") { category = ""; favorites = false; limit = 35 }
                    Button("♡ Favoritos") { category = ""; favorites = true; limit = 35 }
                    Divider()
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 3) {
                            ForEach(categories, id: \.self) { item in
                                Button(item) { category = item; favorites = false; limit = 35 }
                                    .lineLimit(1)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 5)
                            }
                        }
                    }
                }
                .buttonStyle(.plain)
                .padding(12)
                .frame(width: 174)
                .background(.white.opacity(0.07))
                Divider()
                GeometryReader { guideArea83 in
                    // Se aprovecha la altura del monitor sin fabricar canales nuevos.
                    // Con muchos canales las filas mantienen su altura y hay scroll vertical.
                    let visibleRowHeight83 = max(rowHeight,
                        min(90, (guideArea83.size.height - 40) / CGFloat(max(1, shown.count))))
                    ScrollView(.vertical) {
                        HStack(alignment: .top, spacing: 0) {
                            VStack(spacing: 2) {
                                Text("CANAL").frame(width: channelWidth, height: 32, alignment: .leading)
                                    .font(.caption.bold())
                                    .padding(.leading, 7)
                                ForEach(shown) { ch in
                                    Button {
                                        tune(ch.id)
                                        close()
                                    } label: {
                                        HStack(spacing: 8) {
                                            SYNChannelArtworkPill(
                                                name: ch.name,
                                                source: ch.logo,
                                                fallbackSource: ch.fallbackLogo)
                                                .frame(width: 106, height: 43)
                                            Text(ch.name).lineLimit(2)
                                            Spacer(minLength: 0)
                                            if ch.isFavorite {
                                                Image(systemName: "heart.fill")
                                                    .foregroundStyle(.orange)
                                            }
                                        }
                                        .font(.system(size: 11, weight: .medium))
                                        .frame(width: channelWidth - 8, height: visibleRowHeight83, alignment: .leading)
                                        .padding(.leading, 8)
                                        .background(.white.opacity(0.075), in: RoundedRectangle(cornerRadius: 6))
                                    }.buttonStyle(.plain)
                                }
                            }
                            ScrollView(.horizontal) {
                                VStack(spacing: 2) {
                                    HStack(spacing: 0) {
                                        ForEach(0..<totalSlots, id: \.self) { i in
                                            Text(origin.addingTimeInterval(TimeInterval(i) * 1800), format: .dateTime.hour().minute())
                                                .font(.caption)
                                                .frame(width: slotWidth, height: 32, alignment: .leading)
                                        }
                                    }
                                    if shown.isEmpty && !filtered.isEmpty {
                                        HStack(spacing: 10) {
                                            ProgressView().controlSize(.small)
                                            Text("Preparando la guía…")
                                        }
                                        .foregroundStyle(.white.opacity(0.7))
                                        .frame(minWidth: 380, minHeight: 180)
                                    } else {
                                        LazyVStack(spacing: 2) {
                                            ForEach(shown) { channel in row(channel, height: visibleRowHeight83) }
                                        }
                                    }
                                }
                                .background(SYNFullscreenGuideMousePan84())
                            }
                            .id(hourOffset) // Nuevo rango horario: volver al extremo inicial.
                            .frame(width: max(1, guideArea83.size.width - channelWidth), alignment: .leading)
                            .help("Mantén pulsado y arrastra horizontalmente para recorrer la EPG")
                        }
                        if shown.count < filtered.count {
                            Button("Ver más canales (\(shown.count) de \(filtered.count))") { limit += 35 }
                                .padding(12)
                        }
                    }
                    .scrollIndicators(.visible)
                    .frame(width: guideArea83.size.width, height: guideArea83.size.height)
                    .background(Color.white.opacity(0.035))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .buttonStyle(.bordered)
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black)
        .environment(\.colorScheme, .dark)
        .sheet(item: $pendingMargin90) { request in
            SYNEPGMarginChooser90(title: request.title, epgStart: request.start, epgEnd: request.end) { start, end in
                try schedule(request.channelID, request.title, start, end)
            } onClose: {
                pendingMargin90 = nil
            }
        }
        .task(id: "\(category)|\(favorites)|\(query)|\(limit)") {
            await preloadFullGuide77()
        }
    }
}

extension SYNSharedLive70.Stream {
    func bufferSeconds() -> TimeInterval {
        guard let text = try? String(contentsOf: playlist, encoding: .utf8) else { return 0 }
        var durations: [TimeInterval] = []
        for line in text.split(whereSeparator: \.isNewline) where line.hasPrefix("#EXTINF:") {
            let raw = line.dropFirst("#EXTINF:".count).split(separator: ",").first ?? "0"
            if let value = Double(raw) { durations.append(value) }
        }
        return min(360, durations.reduce(0, +))
    }
}

// SYN_FULLSCREEN_GUIDE_84: AppKit pan del timeline, sin bloquear botones ni trackpad.
private struct SYNFullscreenGuideMousePan84: NSViewRepresentable {
    func makeNSView(context: Context) -> SYNFullscreenGuideMousePanView84 {
        SYNFullscreenGuideMousePanView84(frame: .zero)
    }
    func updateNSView(_ view: SYNFullscreenGuideMousePanView84, context: Context) {
        view.scheduleMonitor84()
    }
}

private final class SYNFullscreenGuideMousePanView84: NSView {
    private var monitor84: Any?
    private weak var scroll84: NSScrollView?
    private var down84: NSPoint?
    private var downScrollX84: CGFloat = 0
    private var dragging84 = false

    override func hitTest(_ point: NSPoint) -> NSView? { nil }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        if window == nil { removeMonitor84() }
        else { scheduleMonitor84() }
    }

    func scheduleMonitor84() {
        guard monitor84 == nil else { return }
        DispatchQueue.main.async { [weak self] in self?.installMonitor84() }
    }

    private func installMonitor84() {
        guard monitor84 == nil, window != nil else { return }
        var ancestor: NSView? = superview
        while let node = ancestor {
            if let scroll = node as? NSScrollView {
                scroll84 = scroll
                break
            }
            ancestor = node.superview
        }
        guard scroll84 != nil else { return }
        monitor84 = NSEvent.addLocalMonitorForEvents(matching: [
            .leftMouseDown, .leftMouseDragged, .leftMouseUp
        ]) { [weak self] event in
            self?.handleEvent84(event)
            return event // No interceptar controles ni la interacción de VLC.
        }
    }

    private func handleEvent84(_ event: NSEvent) {
        guard let scroll = scroll84,
              let ownWindow = window,
              event.window === ownWindow else { return }
        let clip = scroll.contentView
        switch event.type {
        case .leftMouseDown:
            let point = clip.convert(event.locationInWindow, from: nil)
            if clip.bounds.contains(point) {
                down84 = event.locationInWindow
                downScrollX84 = clip.bounds.origin.x
                dragging84 = false
            } else { down84 = nil; dragging84 = false }
        case .leftMouseDragged:
            guard let down = down84 else { return }
            let dx = event.locationInWindow.x - down.x
            let dy = event.locationInWindow.y - down.y
            if !dragging84 && abs(dx) > 7 && abs(dx) > abs(dy) * 1.2 {
                dragging84 = true
            }
            guard dragging84 else { return }
            let documentWidth = scroll.documentView?.bounds.width ?? clip.bounds.width
            let maxX = max(0, documentWidth - clip.bounds.width)
            let nextX = min(max(0, downScrollX84 - dx), maxX)
            clip.scroll(to: NSPoint(x: nextX, y: clip.bounds.origin.y))
            scroll.reflectScrolledClipView(clip)
        case .leftMouseUp:
            down84 = nil
            dragging84 = false
        default: break
        }
    }

    private func removeMonitor84() {
        if let monitor84 { NSEvent.removeMonitor(monitor84) }
        monitor84 = nil
        scroll84 = nil
        down84 = nil
        dragging84 = false
    }

    deinit {
        if let monitor84 { NSEvent.removeMonitor(monitor84) }
    }
}
