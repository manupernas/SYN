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
    private init() {}

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
        private let ffmpeg = Process()
        private let server = Process()
        private var writer: FileHandle?
        private var recordingTimer: Timer?
        private var seen: Set<String> = []
        private(set) var recordingURL: URL?
        private(set) var failed = false
        // SYN_71_RECORDING_HEALTH: detect a stalled feed and notify UI outside the DVR tab.
        private(set) var lastRecordingError: String?
        private var lastWrittenSegmentAt = Date()
        var isRecording: Bool { writer != nil }

        init?(remote: URL) {
            guard let ffmpegURL = SYNSharedLive70.executable(["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]),
                  let pythonURL = SYNSharedLive70.executable(["/opt/homebrew/bin/python3", "/usr/bin/python3", "/usr/local/bin/python3"]) else { return nil }
            self.remote = remote
            folder = FileManager.default.temporaryDirectory.appendingPathComponent("SYN-LIVE-\(UUID().uuidString)", isDirectory: true)
            playlist = folder.appendingPathComponent("live.m3u8")
            // Bound to localhost only. This HTTP connection is LOCAL, not an Xtream login.
            let port = Int.random(in: 50000...60000)
            local = URL(string: "http://127.0.0.1:\(port)/live.m3u8")!
            do { try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true) }
            catch { return nil }

            server.executableURL = pythonURL
            server.arguments = ["-m", "http.server", "\(port)", "--bind", "127.0.0.1", "--directory", folder.path]
            server.standardOutput = FileHandle.nullDevice
            server.standardError = FileHandle.nullDevice
            do { try server.run() } catch { return nil }

            ffmpeg.executableURL = ffmpegURL
            ffmpeg.arguments = [
                "-nostdin", "-hide_banner", "-loglevel", "error",
                "-user_agent", "VLC/3.0.21 LibVLC/3.0.21",
                "-i", remote.absoluteString,
                "-map", "0:v?", "-map", "0:a?", "-c", "copy",
                "-f", "hls", "-hls_time", "2", "-hls_list_size", "180",
                "-hls_flags", "delete_segments+append_list+omit_endlist+program_date_time",
                "-hls_segment_filename", folder.appendingPathComponent("segment_%07d.ts").path,
                playlist.path
            ]
            ffmpeg.standardInput = FileHandle.nullDevice
            ffmpeg.standardOutput = FileHandle.nullDevice
            ffmpeg.standardError = FileHandle.nullDevice // never log URLs with credentials
            do { try ffmpeg.run() } catch {
                server.terminate()
                return nil
            }
        }

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
                    } else if !self.ffmpeg.isRunning || attempts >= 55 {
                        timer.invalidate()
                        completion(false)
                    }
                }
            }
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
            if Date().timeIntervalSince(lastWrittenSegmentAt) > 18 || !ffmpeg.isRunning {
                lastRecordingError = ffmpeg.isRunning ? "No llegan nuevos segmentos del canal" : "FFmpeg ha dejado de recibir el canal"
                recordingTimer?.invalidate()
                recordingTimer = nil
                try? writer.close()
                self.writer = nil
                return
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
            flushPendingAndClose()
            if ffmpeg.isRunning { ffmpeg.terminate() }
            if server.isRunning { server.terminate() }
        }
        deinit {
            if ffmpeg.isRunning { ffmpeg.terminate() }
            if server.isRunning { server.terminate() }
        }
    }

    func session(for url: URL, completion: @escaping (Stream?) -> Void) {
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
        for stream in streams.values { stream.stop() }
        streams.removeAll()
    }
    func releaseUnrecorded(except current: URL?) {
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
}
struct SYNGuideProgramme74: Identifiable, Equatable, Sendable {
    var title: String
    var start: Date
    var end: Date
    var id: String { "\(start.timeIntervalSince1970)|\(title)" }
}

// SYN 7.4 — Fullscreen EPG; same NSWindow as the active VLC canvas.
// Grid occupies the screen, but media/audio stays alive underneath it.
struct SYNFullscreenGuide70: View {
    let channels: [SYNGuideChannel70]
    let tune: (String) -> Void
    let close: () -> Void
    let load: (String) async -> [SYNGuideProgramme74]
    @State private var query = ""
    @State private var favorites = false
    @State private var category = ""
    @State private var limit = 35
    @State private var hourOffset = 0
    @State private var fetched: [String: [SYNGuideProgramme74]] = [:]
    @State private var preparing77 = false
    private let slotWidth: CGFloat = 168
    private let channelWidth: CGFloat = 190
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
    // Solo exponer una secuencia CONTIGUA de filas listas; nunca filas vacías en cascada.
    private var shown: [SYNGuideChannel70] {
        var ready: [SYNGuideChannel70] = []
        for channel in filtered.prefix(limit) {
            guard fetched[channel.id] != nil else { break }
            ready.append(channel)
        }
        return ready
    }

    @MainActor private func preloadFullGuide77() async {
        let missing = Array(filtered.prefix(limit)).map(\.id).filter { fetched[$0] == nil }
        guard !missing.isEmpty else { return }
        preparing77 = true
        var result: [String: [SYNGuideProgramme74]] = [:]
        for start in stride(from: 0, to: missing.count, by: 8) {
            if Task.isCancelled { return }
            let ids = Array(missing[start..<min(start + 8, missing.count)])
            let batch = await withTaskGroup(of: (String, [SYNGuideProgramme74]).self, returning: [(String, [SYNGuideProgramme74])].self) { group in
                for id in ids {
                    group.addTask { (id, await load(id)) }
                }
                var list: [(String, [SYNGuideProgramme74])] = []
                for await pair in group { list.append(pair) }
                return list
            }
            for (id, programmes) in batch { result[id] = programmes }
        }
        guard !Task.isCancelled else { return }
        fetched.merge(result) { _, new in new }
        preparing77 = false
    }
    private var origin: Date {
        let now = Date().addingTimeInterval(TimeInterval(hourOffset) * 3600)
        return Date(timeIntervalSince1970: floor(now.timeIntervalSince1970 / 1800) * 1800)
    }
    private func left(for date: Date) -> CGFloat {
        CGFloat(date.timeIntervalSince(origin) / 1800) * slotWidth
    }
    private func row(_ ch: SYNGuideChannel70) -> some View {
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
                    .frame(width: width, height: rowHeight - 3, alignment: .topLeading)
                    .background(Color(hue: Double(abs(ch.id.hashValue % 10)) / 10, saturation: 0.50, brightness: 0.60), in: RoundedRectangle(cornerRadius: 6))
                    .offset(x: x, y: 1)
                }
            }
            if programs.isEmpty {
                Text("Sin programación disponible")
                    .foregroundStyle(.white.opacity(0.53)).font(.caption)
                    .padding(.leading, 10).frame(height: rowHeight)
            }
        }
        .frame(width: slotWidth * CGFloat(totalSlots), height: rowHeight)
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
                VStack(spacing: 0) {
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
                                        HStack(spacing: 5) {
                                            if ch.isFavorite { Image(systemName: "heart.fill").foregroundStyle(.orange) }
                                            Text(ch.name).lineLimit(1)
                                            Spacer(minLength: 0)
                                        }
                                        .font(.system(size: 12, weight: .medium))
                                        .frame(width: channelWidth - 8, height: rowHeight, alignment: .leading)
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
                                            ForEach(shown) { channel in row(channel) }
                                        }
                                    }
                                }
                            }
                        }
                        if shown.count < filtered.count {
                            Button("Ver más canales (\(shown.count) de \(filtered.count))") { limit += 35 }
                                .padding(12)
                        }
                    }
                }
            }
        }
        .buttonStyle(.bordered)
        .foregroundStyle(.white)
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.93))
        .environment(\.colorScheme, .dark)
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
