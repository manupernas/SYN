import SwiftUI

@main
struct SYNNativeApp: App {
    var body: some Scene {
        WindowGroup("SYN") { ContentView()
                .onOpenURL { url in SYNRecordingWindow93.shared.handle(url) } }
            .defaultSize(width: 1300, height: 790)
            .commands {
                CommandGroup(replacing: .newItem) { }
            }
    }
}


// SYN_RECORDING_PLAYER_93 — Reproductor aislado para grabaciones finales.
// No consulta IPTV, no usa el pool de conexiones y no toca el DVR.
import SwiftUI
import AppKit
import Combine
#if canImport(VLCKit)
import VLCKit
#endif

// SYN_RECORDING_IN_WINDOW_94: puente compatible con botones 9.3 y synrec://.
// No crea NSWindow: utiliza la misma WindowGroup que SYN.
@MainActor
final class SYNRecordingWindow93: ObservableObject {
    static let shared = SYNRecordingWindow93()
    @Published private(set) var file: URL? = nil

    func handle(_ incoming: URL) {
        guard incoming.scheme?.lowercased() == "synrec", incoming.host == "open",
              let items = URLComponents(url: incoming, resolvingAgainstBaseURL: false)?.queryItems,
              let path = items.first(where: { $0.name == "path" })?.value else { return }
        open(URL(fileURLWithPath: path))
    }

    func open(_ candidate: URL) {
        let selected = candidate.standardizedFileURL
        let extensions: Set<String> = ["mkv", "mp4", "mov", "m4v", "ts", "avi", "webm"]
        guard selected.isFileURL, extensions.contains(selected.pathExtension.lowercased()),
              FileManager.default.fileExists(atPath: selected.path) else {
            let alert = NSAlert()
            alert.messageText = "No encuentro esta grabación"
            alert.informativeText = "Comprueba que el archivo siga en su carpeta y que el disco esté conectado."
            alert.runModal()
            return
        }
        file = selected
        NotificationCenter.default.post(name: .synRecordingPlayback94Changed,
                                        object: nil, userInfo: ["active": true])
        NSApp.activate(ignoringOtherApps: true)
    }

    func close() {
        file = nil
        NotificationCenter.default.post(name: .synRecordingPlayback94Changed,
                                        object: nil, userInfo: ["active": false])
    }

    func toggleFullscreen() {
        // Fullscreen de la MISMA ventana SYN; no se crea otra ventana.
        (NSApp.keyWindow ?? NSApp.mainWindow)?.toggleFullScreen(nil)
    }
}

extension Notification.Name {
    static let synRecordingPlayback94Changed = Notification.Name("SYNRecordingPlayback94Changed")
}

#if canImport(VLCKit)
@MainActor
private final class SYNRecordingVLC93: ObservableObject {
    @Published var isPlaying = false
    @Published var isSeekable = false
    @Published var duration: Double = 0
    @Published var current: Double = 0
    @Published var seekPosition: Double = 0
    @Published var volume: Double = 80
    @Published var message = ""
    @Published var renderers: [VLCRendererItem] = []
    @Published var castingTo: String? = nil
    let mediaPlayer = VLCMediaPlayer()
    private var started = false
    private let file: URL
    private var discoverers: [VLCRendererDiscoverer] = []

    init(file: URL) { self.file = file }
    func attach(_ canvas: NSView) {
        mediaPlayer.drawable = canvas
        guard !started else { return }
        started = true
        mediaPlayer.media = VLCMedia(url: file)
        mediaPlayer.audio?.volume = Int32(volume)
        mediaPlayer.play()
        isPlaying = true
    }
    func tick(scrubbing: Bool) {
        let ms = max(0, Double(mediaPlayer.media?.length.intValue ?? 0))
        let fallback = max(0, Double(mediaPlayer.time.intValue))
        duration = ms > 0 ? ms / 1000 : 0
        current = max(0, fallback / 1000)
        isPlaying = mediaPlayer.isPlaying
        isSeekable = mediaPlayer.isSeekable && duration > 0
        if !scrubbing && duration > 0 { seekPosition = min(1, max(0, current / duration)) }
    }
    func seek(_ normalized: Double) {
        guard isSeekable else { return }
        mediaPlayer.position = Float(min(0.9999, max(0, normalized)))
    }
    func jump(_ seconds: Double) {
        guard isSeekable, duration > 0 else { return }
        seek((current + seconds) / duration)
    }
    func togglePause() {
        if mediaPlayer.isPlaying { mediaPlayer.pause(); isPlaying = false }
        else { mediaPlayer.play(); isPlaying = true }
    }
    func setVolume(_ n: Double) { mediaPlayer.audio?.volume = Int32(max(0, min(100, n))) }

    func discoverChromecasts() {
        for d in discoverers { d.stop() }
        discoverers.removeAll()
        renderers = []
        message = "Buscando dispositivos Chromecast…"
        for kind in VLCRendererDiscoverer.list() ?? [] {
            guard let d = VLCRendererDiscoverer(name: kind.name),
                  kind.name.localizedCaseInsensitiveContains("chromecast") else { continue }
            if d.start() { discoverers.append(d) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { [weak self] in
            guard let self else { return }
            self.renderers = self.discoverers.flatMap { $0.renderers }
                .filter { $0.type.lowercased() == "chromecast" }
            self.message = self.renderers.isEmpty ? "No se ha encontrado ningún Chromecast en la red." : "Elige un dispositivo Chromecast."
        }
    }
    func cast(to item: VLCRendererItem) {
        let saved = seekPosition
        mediaPlayer.stop()
        if mediaPlayer.setRendererItem(item) {
            castingTo = item.name
            mediaPlayer.media = VLCMedia(url: file)
            mediaPlayer.play()
            restorePosition(saved)
            message = "Enviando a \(item.name). El dispositivo debe aceptar el formato y códecs del vídeo."
        } else {
            castingTo = nil
            mediaPlayer.setRendererItem(nil)
            mediaPlayer.media = VLCMedia(url: file)
            mediaPlayer.play()
            restorePosition(saved)
            message = "VLCKit no pudo iniciar Chromecast."
        }
    }
    func stopCasting() {
        let saved = seekPosition
        mediaPlayer.stop()
        mediaPlayer.setRendererItem(nil)
        castingTo = nil
        mediaPlayer.media = VLCMedia(url: file)
        mediaPlayer.play()
        restorePosition(saved)
        message = "Reproduciendo en este Mac."
    }
    private func restorePosition(_ value: Double) {
        guard value > 0 else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.4) { [weak self] in
            self?.seek(value)
        }
    }
    func stop() {
        mediaPlayer.stop()
        for d in discoverers { d.stop() }
        discoverers.removeAll()
    }
}

private struct SYNRecordingCanvas93: NSViewRepresentable {
    @ObservedObject var playback: SYNRecordingVLC93
    func makeNSView(context: Context) -> NSView {
        let v = NSView(frame: .zero)
        v.wantsLayer = true
        v.layer?.backgroundColor = NSColor.black.cgColor
        DispatchQueue.main.async { playback.attach(v) }
        return v
    }
    func updateNSView(_ view: NSView, context: Context) { }
}

// SYN_DVR_HUD_98 — mismo comportamiento que el directo: mini con autohide,
// fullscreen por clic sobre el vídeo; controles completamente ocultables.
struct SYNRecordingPlayback93: View {
    let file: URL
    var fullscreen: Bool = false
    @StateObject private var playback: SYNRecordingVLC93
    @State private var scrubbing = false
    @State private var hudVisible = false
    @State private var hideTask98: Task<Void, Never>? = nil
    // SYN_RECORDING_ZOOM_99: ignora hover mientras se estabiliza el cambio de tamaño.
    @State private var zoomTransitioning99 = false
    @State private var zoomEndTask99: Task<Void, Never>? = nil

    init(file: URL, fullscreen: Bool = false) {
        self.file = file
        self.fullscreen = fullscreen
        _playback = StateObject(wrappedValue: SYNRecordingVLC93(file: file))
    }

    private func clock(_ seconds: Double) -> String {
        guard seconds.isFinite, seconds >= 0 else { return "00:00" }
        let n = Int(seconds)
        if n >= 3600 { return String(format: "%d:%02d:%02d", n / 3600, (n % 3600) / 60, n % 60) }
        return String(format: "%02d:%02d", n / 60, n % 60)
    }

    private func revealMini98() {
        guard !fullscreen else { return }
        hideTask98?.cancel()
        withAnimation(.easeInOut(duration: 0.20)) { hudVisible = true }
        hideTask98 = Task { @MainActor in
            do { try await Task.sleep(for: .seconds(5)) } catch { return }
            guard !Task.isCancelled, !scrubbing else { return }
            withAnimation(.easeInOut(duration: 0.30)) { hudVisible = false }
        }
    }
    private func concealMini98() {
        hideTask98?.cancel()
        withAnimation(.easeInOut(duration: 0.24)) { hudVisible = false }
    }
    private func tool98(_ symbol: String, tip: String, action: @escaping () -> Void) -> some View {
        Button {
            action()
            if !fullscreen { revealMini98() }
        } label: {
            Image(systemName: symbol)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 33, height: 33)
                .foregroundStyle(.white)
                .background(.white.opacity(0.095), in: RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .help(tip)
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            Color.black
            SYNRecordingCanvas93(playback: playback)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .contentShape(Rectangle())
                .onTapGesture {
                    guard !zoomTransitioning99 else { return }
                    if fullscreen {
                        withAnimation(.easeInOut(duration: 0.24)) { hudVisible.toggle() }
                    } else { revealMini98() }
                }
            if hudVisible {
                VStack(spacing: 0) {
                    if fullscreen {
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(file.deletingPathExtension().lastPathComponent)
                                    .font(.system(size: 15, weight: .semibold))
                                    .lineLimit(1)
                                Text("GRABACIÓN · SYN DVR")
                                    .font(.system(size: 10, weight: .medium))
                                    .foregroundStyle(.white.opacity(0.7))
                            }
                            Spacer()
                            tool98("arrow.down.right.and.arrow.up.left", tip: "Salir de pantalla completa") {
                                SYNRecordingWindow93.shared.toggleFullscreen()
                            }
                        }
                        .padding(.horizontal, 18)
                        .padding(.vertical, 16)
                        .background(LinearGradient(colors: [.black.opacity(0.75), .clear],
                                                   startPoint: .top, endPoint: .bottom))
                    }
                    Spacer(minLength: 0)
                    VStack(alignment: .leading, spacing: 9) {
                        if !fullscreen {
                            HStack(spacing: 8) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(file.deletingPathExtension().lastPathComponent)
                                        .font(.system(size: 13, weight: .semibold))
                                        .lineLimit(1)
                                    Text("GRABACIÓN · SYN DVR")
                                        .font(.system(size: 10, weight: .medium))
                                        .foregroundStyle(.white.opacity(0.72))
                                }
                                Spacer()
                            }
                        }
                        HStack(spacing: 9) {
                            Text(clock(playback.current)).monospacedDigit()
                            Slider(value: $playback.seekPosition, in: 0...1, onEditingChanged: { active in
                                scrubbing = active
                                if active { hideTask98?.cancel() }
                                else {
                                    playback.seek(playback.seekPosition)
                                    if !fullscreen { revealMini98() }
                                }
                            })
                            .disabled(!playback.isSeekable)
                            .help("Desplazarse por la grabación")
                            Text(clock(playback.duration)).monospacedDigit()
                        }
                        .font(.system(size: 11, weight: .medium))
                        HStack(spacing: 7) {
                            tool98("gobackward.15", tip: "Retroceder 15 segundos") { playback.jump(-15) }
                            tool98(playback.isPlaying ? "pause.fill" : "play.fill", tip: "Pausar o reproducir") {
                                playback.togglePause()
                            }
                            tool98("goforward.15", tip: "Avanzar 15 segundos") { playback.jump(15) }
                            Spacer(minLength: 0)
                            Image(systemName: "speaker.wave.2").font(.system(size: 13))
                            Slider(value: $playback.volume, in: 0...100)
                                .frame(width: fullscreen ? 105 : 75)
                                .tint(.orange)
                                .onChange(of: playback.volume) { _, value in
                                    playback.setVolume(value)
                                    if !fullscreen { revealMini98() }
                                }
                            Menu {
                                Button("Buscar Chromecast") { playback.discoverChromecasts() }
                                ForEach(Array(playback.renderers.enumerated()), id: \.offset) { _, item in
                                    Button(item.name) { playback.cast(to: item) }
                                }
                                if playback.castingTo != nil {
                                    Divider()
                                    Button("Volver a este Mac") { playback.stopCasting() }
                                }
                            } label: {
                                Image(systemName: "tv").font(.system(size: 13))
                            }
                            .help("Chromecast")
                            Button {
                                if let u = URL(string: "x-apple.systempreferences:com.apple.Displays-Settings.extension") {
                                    NSWorkspace.shared.open(u)
                                }
                            } label: {
                                Image(systemName: "airplayvideo").font(.system(size: 13))
                            }
                            .help("AirPlay · duplicación de pantalla de macOS")
                            tool98(fullscreen ? "arrow.down.right.and.arrow.up.left" :
                                      "arrow.up.left.and.arrow.down.right",
                                   tip: fullscreen ? "Salir de pantalla completa" : "Pantalla completa") {
                                SYNRecordingWindow93.shared.toggleFullscreen()
                            }
                        }
                        .buttonStyle(.plain)
                        if !playback.message.isEmpty {
                            Text(playback.message)
                                .font(.system(size: 11))
                                .foregroundStyle(.orange)
                                .lineLimit(2)
                        }
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 17)
                    .padding(.top, fullscreen ? 15 : 34)
                    .padding(.bottom, 13)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(LinearGradient(colors: [.clear, .black.opacity(0.58), .black.opacity(0.89)],
                                               startPoint: .top, endPoint: .bottom))
                }
                .transition(.opacity)
            }
        }
        .contentShape(Rectangle())
        .onHover { inside in
            guard !zoomTransitioning99 else { return }
            if !fullscreen {
                if inside { revealMini98() } else { concealMini98() }
            }
        }
        .onContinuousHover { phase in
            guard !zoomTransitioning99 else { return }
            if !fullscreen, case .active = phase { revealMini98() }
        }
        .onChange(of: fullscreen) { _, _ in
            hideTask98?.cancel()
            zoomEndTask99?.cancel()
            zoomTransitioning99 = true
            withAnimation(.easeInOut(duration: 0.20)) { hudVisible = false }
            zoomEndTask99 = Task { @MainActor in
                do { try await Task.sleep(for: .milliseconds(440)) } catch { return }
                guard !Task.isCancelled else { return }
                zoomTransitioning99 = false
            }
        }
        .onReceive(Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()) { _ in
            playback.tick(scrubbing: scrubbing)
        }
        .onDisappear {
            hideTask98?.cancel()
            zoomEndTask99?.cancel()
            playback.stop()
        }
    }
}
#else
struct SYNRecordingPlayback93: View {
    let file: URL
    var fullscreen: Bool = false
    var body: some View { Text("VLCKit no está disponible en esta compilación.") }
}
#endif
