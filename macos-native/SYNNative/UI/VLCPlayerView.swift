import AppKit
import SwiftUI
#if canImport(VLCKit)
import VLCKit
#endif

// SYN Native Alpha 2.6: one VLC player and one drawable, even during fullscreen.
// The full-screen controls are AppKit overlays; no second streaming connection is created.
final class SYNFullscreenWindow: NSWindow, NSWindowDelegate {
    var onFullscreenEntryFailure794: (() -> Void)?
    func windowDidFailToEnterFullScreen(_ window: NSWindow) {
        onFullscreenEntryFailure794?()
    }
    var onEscape: (() -> Void)?
    var onTogglePause: (() -> Void)?
    var onSeekBack: (() -> Void)?
    var onSeekForward: (() -> Void)?
    var onSnapshot: (() -> Void)?

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }

    override func keyDown(with event: NSEvent) {
        switch event.keyCode {
        case 53: onEscape?()                // Esc
        case 49: onTogglePause?()           // Space
        case 123: onSeekBack?()             // Left
        case 124: onSeekForward?()          // Right
        case 8 where event.modifierFlags.contains(.command): onSnapshot?() // Cmd+C
        default: super.keyDown(with: event)
        }
    }
}

// Black dim for fullscreen only, never captures mouse events.
private final class SYNFullscreenUniformDim621: NSView {
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
}

final class SYNVideoHost: NSView {
    private let canvas = NSView()
    private var canvasConstraints: [NSLayoutConstraint] = []
    private var currentURL: URL?
    private var fullWindow: SYNFullscreenWindow?
    private weak var originalWindow: NSWindow?
    private var topBar: NSView?
    private var bottomBar: NSView?
    private var localMouseMonitor: Any?
    private var hideJob: DispatchWorkItem?
    private var cursorHidden = false
    // SYN_FULLSCREEN_SAFE_DOCK_793
    // Fullscreen personalizado sin cambiar preferencias globales del Dock o menú.
    // Mission Control y las demás pantallas quedan gestionados por macOS.
    // SYN_NATIVE_SPACE_FULLSCREEN_794
    // Fullscreen auténtico de macOS, gestionado POR MONITOR y sin NSApp.presentationOptions.
    private var nativeEnterObserver794: NSObjectProtocol?
    private var nativeExitObserver794: NSObjectProtocol?
    private var nativeEntering794 = false
    private var nativeExitRequested794 = false
    private var nativeMinimizeRequested794 = false
    private var fullscreenPauseButton: NSButton?
    private var embeddedPauseButton: NSButton?
    private var pausedByUser = false
    private var volumeValue: Double = 80
    private var muted = false
    private var slider: NSSlider?
    private var channelLabel: NSTextField?
    // SYN_FS_CLICK_PURO_621: no gradients, no movement reveal, no timer.
    private var synUniformDim621: SYNFullscreenUniformDim621?
    private var synHUDIsVisible621 = false
    private var progressTrack: NSView?
    // SYN_FS_GTK_59 — fullscreen mantiene el mismo canvas VLCKit.
    var onPreviousChannel: (() -> Void)?
    var onNextChannel: (() -> Void)?
    var onOpenGuide: (() -> Void)?
    // SYN_FULLSCREEN_70: fullscreen model, actual EPG and one upstream connection.
    var programNow70 = SYNProgram70(title: "", start: nil, end: nil)
    var programNext70 = SYNProgram70(title: "", start: nil, end: nil)
    var guideChannels70: [SYNGuideChannel70] = []
    var onGuideRefresh70: (() -> Void)?
    var onLoadGuideProgrammes74: ((String) async -> [SYNGuideProgramme74])?
    var onSelectChannel70: ((String) -> Void)?
    private var guidePanel70: NSView?
    // SYN_AIRPLAY_FULLSCREEN_797: AirPlay vive solo en el Space fullscreen.
    // El HLS local compartido sigue alimentando DVR; VLC deja de reproducir.
    private let airPlay797 = SYNAirPlayPlayback796()
    private var airPlayPanel797: NSView?
    private var liveSession70: SYNSharedLive70.Stream?
    private var loadSerial70 = 0
    private var replaying70 = false
    private var recButton70: NSButton?
    private var nowLabel70: NSTextField?
    private var nextLabel70: NSTextField?
    private var timeLabel70: NSTextField?
    private var programProgress70: NSProgressIndicator?
    private var timeShiftSlider70: NSSlider?
    private var tick70: Timer?
    // SYN_72_FULLSCREEN_NAME_CLEAN: solo cambia la etiqueta visual.
    // Xtream, URLs, IDs y preferencias siguen usando el nombre original.
    private static func cleanChannelName72(_ title: String) -> String {
        let raw = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = #"^\s*(?:(?:\|\s*)?(?:ES|ESP|SPAIN|LAT|LATAM|US|USA|UK|GB|MX|AR|CL|CO|PE|PT|FR|DE|IT|BR)(?:\s*\|\s*|\s*[:\-–]\s*))+"#
        let cleaned = raw.replacingOccurrences(of: pattern, with: "", options: [.regularExpression, .caseInsensitive])
            .replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? raw : cleaned
    }
    private var channelTitle = "Televisión en directo"
    func configureTitle(_ title: String) {
        channelTitle = title
        channelLabel?.stringValue = Self.cleanChannelName72(title)
    }

    #if canImport(VLCKit)
    private let player = VLCMediaPlayer()
    #endif

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = NSColor.black.cgColor
        canvas.wantsLayer = true
        canvas.layer?.backgroundColor = NSColor.black.cgColor
        addSubview(canvas)
        installCanvasConstraints()
        #if canImport(VLCKit)
        player.drawable = canvas
        player.audio?.volume = 80
        #endif
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) no implementado") }

    private func installCanvasConstraints() {
        canvas.translatesAutoresizingMaskIntoConstraints = false
        canvasConstraints = [
            canvas.leadingAnchor.constraint(equalTo: leadingAnchor),
            canvas.trailingAnchor.constraint(equalTo: trailingAnchor),
            canvas.topAnchor.constraint(equalTo: topAnchor),
            canvas.bottomAnchor.constraint(equalTo: bottomAnchor)
        ]
        NSLayoutConstraint.activate(canvasConstraints)
    }

    // Exactly ONE provider media stream: FFmpeg ingests it; VLC plays local HLS.
    // Changing channels while REC is active keeps the previous local feed recording,
    // opening a second provider stream only for the *different* channel.
    func play(_ url: URL?) {
        guard currentURL != url else { return }
        // Si cambiamos de canal durante AirPlay, limpiar la ruta externa antes
        // de sintonizar la siguiente fuente y sin reabrir el canal anterior.
        if airPlay797.player != nil { stopAirPlay797(restoreVLC: false) }
        currentURL = url
        loadSerial70 += 1
        let serial = loadSerial70
        liveSession70 = nil
        replaying70 = false
        pausedByUser = false
        refreshPauseButtons()
        #if canImport(VLCKit)
        player.stop()
        #endif
        SYNSharedLive70.shared.releaseUnrecorded(except: url)
        guard let url else { return }
        if url.pathComponents.contains("live") {
            SYNSharedLive70.shared.session(for: url) { [weak self] session in
                guard let self, self.loadSerial70 == serial, self.currentURL == url else { return }
                self.liveSession70 = session
                self.playMedia70(session?.local ?? url)
                self.updateRecording70()
            }
        } else {
            playMedia70(url)
        }
    }

    private func playMedia70(_ url: URL) {
        #if canImport(VLCKit)
        let media = VLCMedia(url: url)
        media.addOption(":http-user-agent=VLC/3.0.21 LibVLC/3.0.21")
        // Valores avanzados, conservadores por defecto; no tocan DVR ni la URL.
        let savedCache = UserDefaults.standard.integer(forKey: "syn.native.vlc.networkCaching799")
        let cacheMS = [500, 1000, 2000, 3000, 5000].contains(savedCache) ? savedCache : 1000
        media.addOption(":network-caching=\(cacheMS)")
        let hardware = UserDefaults.standard.string(forKey: "syn.native.vlc.hardware799") ?? "auto"
        if hardware == "none" { media.addOption(":avcodec-hw=none") }
        player.media = media
        player.play()
        player.audio?.volume = Int32(muted ? 0 : volumeValue)
        #endif
    }

    func pauseOrResume() {
        #if canImport(VLCKit)
        if player.isPlaying { player.pause(); pausedByUser = true }
        else { player.play(); pausedByUser = false }
        #endif
        refreshPauseButtons()
    }
    private func refreshPauseButtons() {
        let symbol = pausedByUser ? "play.fill" : "pause.fill"
        fullscreenPauseButton?.image = NSImage(systemSymbolName: symbol, accessibilityDescription: "Reproducción o pausa")
    }
    func setVolume(_ value: Double) {
        volumeValue = max(0, min(value, 100))
        #if canImport(VLCKit)
        player.audio?.volume = Int32(muted ? 0 : volumeValue)
        #endif
        slider?.doubleValue = volumeValue
    }
    @objc private func toggleMute() {
        muted.toggle()
        setVolume(volumeValue)
    }
    @objc private func sliderChanged(_ sender: NSSlider) {
        muted = false
        setVolume(sender.doubleValue)
    }
    @objc private func pauseClicked() { pauseOrResume() }
    @objc private func zapPrevious59() { onPreviousChannel?() }
    @objc private func zapNext59() { onNextChannel?() }
    @objc private func openGuide59() { onOpenGuide?(); exitFullscreen() }
    func embeddedSeekBack() { seek(seconds: -10) }
    func embeddedSeekForward() { seek(seconds: 10) }
    func embeddedSnapshot() { snapshot() }
    func embeddedToggleMute() { toggleMute() }
    func embeddedSetMuted(_ value: Bool) {
        if muted != value { toggleMute() }
    }


    private func seek(seconds: Float) {
        #if canImport(VLCKit)
        if replaying70 && player.isSeekable {
            let duration = Float(player.media?.length.intValue ?? 0) / 1000
            if duration > 0 {
                player.position = max(0, min(0.995, player.position + seconds / duration))
                return
            }
        }
        guard let stream = liveSession70, let snapshot = stream.replaySnapshot() else {
            NSSound.beep(); return
        }
        let target = max(0, snapshot.duration - Double(max(30, -seconds)))
        startReplay70(snapshot: snapshot, targetSeconds: target)
        #endif
    }
    private func startReplay70(snapshot: (url: URL, duration: TimeInterval), targetSeconds: Double) {
        #if canImport(VLCKit)
        replaying70 = true
        playMedia70(snapshot.url)
        let desired = Float(max(0, min(0.995, targetSeconds / snapshot.duration)))
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.4) { [weak self] in
            guard let self, self.replaying70 else { return }
            self.player.position = desired
        }
        #endif
    }
    @objc private func seekBackward() { seek(seconds: -30) }
    @objc private func seekForward() { seek(seconds: 30) }
    @objc private func returnToLive() {
        guard let stream = liveSession70 else { NSSound.beep(); return }
        replaying70 = false
        playMedia70(stream.local) // always local: no second Xtream connection
        timeShiftSlider70?.doubleValue = 0
    }
    @objc private func timeShiftChanged70(_ sender: NSSlider) {
        guard let stream = liveSession70, let snapshot = stream.replaySnapshot() else {
            NSSound.beep(); return
        }
        startReplay70(snapshot: snapshot, targetSeconds: max(0, snapshot.duration + sender.doubleValue))
    }
    @objc private func toggleREC70() {
        guard let session = liveSession70 else { NSSound.beep(); return }
        if session.isRecording { session.stopRecording() }
        else {
            do { try session.beginRecording() }
            catch { NSAlert(error: error).runModal() }
        }
        updateRecording70()
        SYNSharedLive70.shared.releaseUnrecorded(except: currentURL)
    }
    // SYN_MINI_STATUS_795: same live recorder used by fullscreen; no duplicate feed.
    func synMiniCanRecord795() -> Bool { liveSession70 != nil }
    func synMiniIsRecording795() -> Bool { liveSession70?.isRecording ?? false }
    func synMiniToggleRecording795() { toggleREC70() }
    func synMiniActualResolution795() -> String {
        #if canImport(VLCKit)
        let dimensions = player.videoSize
        let width = Int(dimensions.width.rounded())
        let height = Int(dimensions.height.rounded())
        if width > 0 && height > 0 { return "\(width) × \(height) px" }
        #endif
        return "Resolución pendiente"
    }

    private func updateRecording70() {
        let active = liveSession70?.isRecording ?? false
        recButton70?.title = active ? "■ REC" : "● REC"
        recButton70?.contentTintColor = active ? .systemRed : .white
        recButton70?.toolTip = active ? "Detener grabación del canal actual" : "Grabar este canal usando su única conexión"
    }
    func configurePrograms70(now: SYNProgram70, next: SYNProgram70) {
        programNow70 = now
        programNext70 = next
        nowLabel70?.stringValue = now.title.isEmpty ? "Ahora · Sin EPG" : "Ahora · " + now.title
        nextLabel70?.stringValue = next.title.isEmpty ? "A continuación · Sin datos" : "A continuación · " + next.title
        refreshProgramProgress70()
    }
    private func refreshProgramProgress70() {
        guard let start = programNow70.start, let end = programNow70.end, end > start else {
            programProgress70?.doubleValue = 0
            timeLabel70?.stringValue = "DIRECTO"
            return
        }
        let total = end.timeIntervalSince(start)
        programProgress70?.doubleValue = min(100, max(0, Date().timeIntervalSince(start) / total * 100))
        timeLabel70?.stringValue = "\(start.formatted(date: .omitted, time: .shortened))  –  \(end.formatted(date: .omitted, time: .shortened))"
    }
    @objc private func updateClock70() {
        // Refrescar el estado del receptor sin crear un segundo reproductor.
        if airPlay797.player != nil {
            let hadRoute = airPlay797.hadExternalRoute
            airPlay797.refresh()
            if hadRoute && !airPlay797.externalActive {
                stopAirPlay797(restoreVLC: true)
            }
        }
        refreshProgramProgress70()
        updateRecording70()
        #if canImport(VLCKit)
        let canSeek = liveSession70 != nil && (liveSession70?.bufferSeconds() ?? 0) > 10
        timeShiftSlider70?.isEnabled = canSeek
        if canSeek {
            let seconds = Double(liveSession70?.bufferSeconds() ?? 0)
            timeShiftSlider70?.minValue = -min(360, seconds)
            if !replaying70 { timeShiftSlider70?.doubleValue = 0 }
        }
        #endif
    }
    @objc private func snapshot() {
        #if canImport(VLCKit)
        guard currentURL != nil else { NSSound.beep(); return }
        let fm = FileManager.default
        let pictures = fm.urls(for: .picturesDirectory, in: .userDomainMask).first
            ?? fm.homeDirectoryForCurrentUser.appendingPathComponent("Pictures")
        let folder = pictures.appendingPathComponent("SYN Capturas", isDirectory: true)
        do {
            try fm.createDirectory(at: folder, withIntermediateDirectories: true)
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy-MM-dd_HH-mm-ss-SSS"
            let target = folder.appendingPathComponent("SYN_\(formatter.string(from: Date())).png")
            player.saveVideoSnapshot(at: target.path, withWidth: 0, andHeight: 0)
            print("[SYN] Captura solicitada en Imágenes/SYN Capturas")
        } catch { print("[SYN] Captura: \(error.localizedDescription)") }
        #endif
    }

    private func button(_ symbol: String, tip: String, action: Selector) -> NSButton {
        let b = NSButton(title: "", target: self, action: action)
        b.isBordered = false
        b.image = NSImage(systemSymbolName: symbol, accessibilityDescription: tip)
        b.contentTintColor = .white
        b.toolTip = tip
        b.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            b.widthAnchor.constraint(equalToConstant: 34),
            b.heightAnchor.constraint(equalToConstant: 32)
        ])
        return b
    }

    // Alpha 2.8: closer to Apple TV fullscreen reference. Real functions only.
    private func glass70(_ content: NSView, radius: CGFloat) -> NSView {
        if #available(macOS 26.0, *) {
            let v = NSGlassEffectView()
            v.cornerRadius = radius
            v.tintColor = nil // IMPORTANT: never use the app teal accent here.
            v.contentView = content // Real Liquid Glass; content is INSIDE the effect.
            v.appearance = NSAppearance(named: .darkAqua)
            return v
        }
        let fallback = NSVisualEffectView()
        fallback.material = .hudWindow
        fallback.blendingMode = .behindWindow
        fallback.state = .active
        fallback.wantsLayer = true
        fallback.layer?.cornerRadius = radius
        fallback.addSubview(content)
        content.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: fallback.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: fallback.trailingAnchor),
            content.topAnchor.constraint(equalTo: fallback.topAnchor),
            content.bottomAnchor.constraint(equalTo: fallback.bottomAnchor)
        ])
        return fallback
    }

    private func text70(_ value: String, size: CGFloat, weight: NSFont.Weight = .regular) -> NSTextField {
        let label = NSTextField(labelWithString: value)
        label.textColor = .white
        label.font = .systemFont(ofSize: size, weight: weight)
        label.lineBreakMode = .byTruncatingTail
        return label
    }

    // SYN_71_HUD_LAYOUT — one broad glass panel, three orderly full-width rows.
    private func makeBottomBar(in parent: NSView) -> NSView {
        let root = NSView()
        root.translatesAutoresizingMaskIntoConstraints = false
        parent.addSubview(root)

        let title = text70(Self.cleanChannelName72(channelTitle), size: 19, weight: .semibold)
        channelLabel = title
        title.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let now = text70("Ahora · Sin EPG", size: 14, weight: .medium)
        let next = text70("A continuación · Sin datos", size: 12)
        next.textColor = .secondaryLabelColor
        nowLabel70 = now; nextLabel70 = next
        // Canal, Ahora, A continuación y horario: todos juntos, alineados a IZQUIERDA.
        let timing = text70("DIRECTO", size: 11, weight: .medium)
        timing.textColor = .secondaryLabelColor
        timeLabel70 = timing
        let programme = NSStackView(views: [title, now, next, timing])
        programme.orientation = .vertical
        programme.alignment = .leading
        programme.distribution = .fill
        programme.spacing = 5
        title.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        now.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        next.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        let progress = NSProgressIndicator()
        progress.style = .bar
        progress.isIndeterminate = false
        progress.minValue = 0; progress.maxValue = 100
        progress.doubleValue = 0
        progress.widthAnchor.constraint(equalToConstant: 135).isActive = true
        programProgress70 = progress
        let shiftTitle = text70("TIMESHIFT", size: 11, weight: .medium)
        shiftTitle.textColor = .secondaryLabelColor
        let shift = NSSlider(value: 0, minValue: -360, maxValue: 0,
                             target: self, action: #selector(timeShiftChanged70(_:)))
        shift.isEnabled = false
        shift.setContentHuggingPriority(.defaultLow, for: .horizontal)
        shift.widthAnchor.constraint(greaterThanOrEqualToConstant: 100).isActive = true
        timeShiftSlider70 = shift
        let timeline = NSStackView(views: [progress, shiftTitle, shift])
        timeline.orientation = .horizontal
        timeline.alignment = .centerY
        timeline.spacing = 16
        timeline.distribution = .fill

        let back = button("gobackward.30", tip: "Retroceder 30 s (timeshift)", action: #selector(seekBackward))
        let pause = button("pause.fill", tip: "Pausar/reanudar", action: #selector(pauseClicked))
        fullscreenPauseButton = pause
        let forward = button("goforward.30", tip: "Avanzar 30 s (timeshift)", action: #selector(seekForward))
        let live = button("dot.radiowaves.left.and.right", tip: "Volver al directo", action: #selector(returnToLive))
        let rec = NSButton(title: "● REC", target: self, action: #selector(toggleREC70))
        rec.isBordered = false
        rec.font = .systemFont(ofSize: 13, weight: .semibold)
        rec.contentTintColor = .white
        recButton70 = rec
        let photo = button("camera", tip: "Capturar fotograma", action: #selector(snapshot))
        let mute = button("speaker.wave.2", tip: "Silenciar", action: #selector(toggleMute))
        let volume = NSSlider(value: volumeValue, minValue: 0, maxValue: 100,
                              target: self, action: #selector(sliderChanged(_:)))
        volume.widthAnchor.constraint(equalToConstant: 130).isActive = true
        slider = volume
        let transport = NSStackView(views: [back, pause, forward, live, rec, photo])
        transport.orientation = .horizontal
        transport.alignment = .centerY
        transport.spacing = 13
        let audio = NSStackView(views: [mute, volume])
        audio.orientation = .horizontal
        audio.alignment = .centerY
        audio.spacing = 8
        let controls = NSStackView(views: [transport, audio])
        controls.orientation = .horizontal
        controls.distribution = .equalSpacing
        controls.alignment = .centerY
        controls.spacing = 20

        // SYN_721_INFO_LEFT_ANCHOR
        // No basta alinear las etiquetas: se ancla el BLOQUE al lado izquierdo.
        let layout = NSView()
        layout.translatesAutoresizingMaskIntoConstraints = false
        programme.translatesAutoresizingMaskIntoConstraints = false
        timeline.translatesAutoresizingMaskIntoConstraints = false
        controls.translatesAutoresizingMaskIntoConstraints = false
        layout.addSubview(programme)
        layout.addSubview(timeline)
        layout.addSubview(controls)
        NSLayoutConstraint.activate([
            // Información y EPG siempre comienzan en X = 24 dentro del HUD.
            programme.leadingAnchor.constraint(equalTo: layout.leadingAnchor, constant: 24),
            programme.trailingAnchor.constraint(equalTo: layout.trailingAnchor, constant: -24),
            programme.topAnchor.constraint(equalTo: layout.topAnchor, constant: 17),
            // Barra de progreso y timeshift en su propia fila, bajo el texto.
            timeline.leadingAnchor.constraint(equalTo: layout.leadingAnchor, constant: 24),
            timeline.trailingAnchor.constraint(equalTo: layout.trailingAnchor, constant: -24),
            timeline.topAnchor.constraint(equalTo: programme.bottomAnchor, constant: 16),
            // Controles de reproducción a la izquierda; audio a la derecha.
            controls.leadingAnchor.constraint(equalTo: layout.leadingAnchor, constant: 24),
            controls.trailingAnchor.constraint(equalTo: layout.trailingAnchor, constant: -24),
            controls.topAnchor.constraint(greaterThanOrEqualTo: timeline.bottomAnchor, constant: 14),
            controls.bottomAnchor.constraint(equalTo: layout.bottomAnchor, constant: -16)
        ])
        let glass = glass70(layout, radius: 26)
        glass.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(glass)
        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: parent.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: parent.trailingAnchor),
            root.bottomAnchor.constraint(equalTo: parent.bottomAnchor, constant: -14),
            root.heightAnchor.constraint(equalToConstant: 254),
            glass.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            glass.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            glass.topAnchor.constraint(equalTo: root.topAnchor, constant: 4),
            glass.bottomAnchor.constraint(equalTo: root.bottomAnchor, constant: -4)
        ])
        configurePrograms70(now: programNow70, next: programNext70)
        updateRecording70()
        return root
    }

    private func trafficDot(_ color: NSColor, tip: String, action: Selector) -> NSButton {
        let b = NSButton(title: "", target: self, action: action)
        b.isBordered = false
        b.wantsLayer = true
        b.layer?.backgroundColor = color.cgColor
        b.layer?.cornerRadius = 6
        b.toolTip = tip
        b.translatesAutoresizingMaskIntoConstraints = false
        b.widthAnchor.constraint(equalToConstant: 12).isActive = true
        b.heightAnchor.constraint(equalToConstant: 12).isActive = true
        return b
    }
    private func makeTopBar(in parent: NSView) -> NSView {
        let root = NSView()
        root.translatesAutoresizingMaskIntoConstraints = false
        parent.addSubview(root)
        let exit = button("arrow.down.right.and.arrow.up.left", tip: "Salir del fullscreen · Esc", action: #selector(fullscreenExit))
        let photo = button("camera", tip: "Capturar", action: #selector(snapshot))
        let airPlay = button("airplayvideo", tip: "AirPlay en pantalla completa", action: #selector(toggleAirPlay797))
        let previous = button("backward.end.fill", tip: "Canal anterior", action: #selector(zapPrevious59))
        let following = button("forward.end.fill", tip: "Canal siguiente", action: #selector(zapNext59))
        let guide = NSButton(title: "Guía EPG", target: self, action: #selector(openGuide70))
        guide.isBordered = false; guide.font = .systemFont(ofSize: 13, weight: .semibold)
        guide.contentTintColor = .white
        let left = NSStackView(views: [exit])
        let right = NSStackView(views: [previous, following, guide, airPlay, photo])
        for stack in [left, right] {
            stack.orientation = .horizontal
            stack.alignment = .centerY
            stack.spacing = 9
            stack.edgeInsets = NSEdgeInsets(top: 6, left: 10, bottom: 6, right: 10)
        }
        let leftGlass = glass70(left, radius: 22)
        let rightGlass = glass70(right, radius: 22)
        leftGlass.translatesAutoresizingMaskIntoConstraints = false
        rightGlass.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(leftGlass); root.addSubview(rightGlass)
        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: parent.leadingAnchor),
            root.trailingAnchor.constraint(equalTo: parent.trailingAnchor),
            root.topAnchor.constraint(equalTo: parent.topAnchor),
            root.heightAnchor.constraint(equalToConstant: 82),
            leftGlass.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            leftGlass.centerYAnchor.constraint(equalTo: root.centerYAnchor),
            rightGlass.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            rightGlass.centerYAnchor.constraint(equalTo: root.centerYAnchor)
        ])
        root.alphaValue = 0
        return root
    }

    func configureGuide70(channels: [SYNGuideChannel70],
                          tune: @escaping (String) -> Void,
                          refresh: @escaping () -> Void,
                          load: @escaping (String) async -> [SYNGuideProgramme74]) {
        onLoadGuideProgrammes74 = load
        guideChannels70 = channels
        onSelectChannel70 = tune
        onGuideRefresh70 = refresh
        if let existing = guidePanel70 as? NSHostingView<SYNFullscreenGuide70> {
            existing.rootView = SYNFullscreenGuide70(channels: channels,
                tune: { [weak self] id in self?.onSelectChannel70?(id) },
                close: { [weak self] in self?.closeGuide74() },
                load: { [weak self] id in
                    guard let loader = self?.onLoadGuideProgrammes74 else { return [] }
                    return await loader(id)
                })
        }
    }

    // SYN_FIX74_FULLSCREEN: muestra la parrilla EN la misma ventana de VLC.
    // No desmonta canvas, no ejecuta player.stop y no cambia de escritorio.
    @objc private func openGuide70() {
        if guidePanel70 != nil { closeGuide74(); return }
        guard let full = fullWindow, let content = full.contentView else { return }
        setFullscreenHUDVisible621(false)
        let panel = NSHostingView(rootView: SYNFullscreenGuide70(
            channels: guideChannels70,
            tune: { [weak self] id in self?.onSelectChannel70?(id) },
            close: { [weak self] in self?.closeGuide74() },
            load: { [weak self] id in
                guard let loader = self?.onLoadGuideProgrammes74 else { return [] }
                return await loader(id)
            }))
        panel.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(panel)
        NSLayoutConstraint.activate([
            panel.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            panel.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            panel.topAnchor.constraint(equalTo: content.topAnchor),
            panel.bottomAnchor.constraint(equalTo: content.bottomAnchor)
        ])
        guidePanel70 = panel
        onGuideRefresh70?() // Pide datos nuevos si el catálogo/EPG está incompleto.
    }

    private func closeGuide74() {
        guidePanel70?.removeFromSuperview()
        guidePanel70 = nil
        setFullscreenHUDVisible621(false)
    }

    // SYN_AIRPLAY_FULLSCREEN_797 — interfaz SwiftUI embebida en el MISMO
    // NSWindow fullscreen. AVRoutePickerView es el selector nativo oficial.
    // No .sheet, NSPanel ni ventana flotante de vídeo.
    @objc private func toggleAirPlay797() {
        guard fullWindow != nil else { return }
        if airPlay797.player != nil { stopAirPlay797(restoreVLC: true); return }
        guard let source = liveSession70?.local ?? currentURL else { return }
        airPlay797.begin(source)
        guard airPlay797.player != nil, let content = fullWindow?.contentView else { return }
        // Detener SOLO la reproducción VLCKit; el FFmpeg local y el DVR
        // compartido siguen activos sin reconectar al proveedor.
        #if canImport(VLCKit)
        player.stop()
        #endif
        closeGuide74()
        setFullscreenHUDVisible621(false)
        let overlay = NSHostingView(rootView: SYNFullscreenAirPlayPanel797(
            session: airPlay797,
            channel: Self.cleanChannelName72(channelTitle),
            onStop: { [weak self] in self?.stopAirPlay797(restoreVLC: true) },
            onExit: { [weak self] in self?.exitFullscreen() }
        ))
        overlay.translatesAutoresizingMaskIntoConstraints = true
        overlay.frame = content.bounds
        overlay.autoresizingMask = [.width, .height]
        content.addSubview(overlay)
        airPlayPanel797 = overlay
    }

    private func stopAirPlay797(restoreVLC: Bool) {
        guard airPlay797.player != nil || airPlayPanel797 != nil else { return }
        airPlay797.stop()
        airPlayPanel797?.removeFromSuperview()
        airPlayPanel797 = nil
        if restoreVLC, let original = currentURL {
            playMedia70(liveSession70?.local ?? original)
        }
    }

    private func setCursorHidden(_ hidden: Bool) {
        guard hidden != cursorHidden else { return }
        cursorHidden = hidden
        if hidden { NSCursor.hide() } else { NSCursor.unhide() }
    }
    // Both bars and the uniform black dim appear/disappear on video click ONLY.
    private func setFullscreenHUDVisible621(_ visible: Bool) {
        guard fullWindow != nil else { return }
        synHUDIsVisible621 = visible
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.23
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            topBar?.animator().alphaValue = visible ? 1 : 0
            bottomBar?.animator().alphaValue = visible ? 1 : 0
            synUniformDim621?.animator().alphaValue = visible ? 1 : 0
        }
    }

    private func clickOnFullscreenControl621(_ point: NSPoint, in content: NSView) -> Bool {
        guard synHUDIsVisible621 else { return false }
        var view: NSView? = content.hitTest(point)
        while let item = view {
            if item is NSControl { return true }
            view = item.superview
        }
        return false
    }

    func toggleFullscreen() {
        if fullWindow != nil { exitFullscreen() } else { enterFullscreen() }
    }
    private func enterFullscreen() {
        guard fullWindow == nil, let screen = window?.screen ?? NSScreen.main else { return }
        originalWindow = window
        // La ventana con título (oculto) permite activar el fullscreen NATIVO.
        // Con .borderless macOS no crea un Space fullscreen ni oculta su propia barra.
        let full = SYNFullscreenWindow(contentRect: screen.visibleFrame,
                                        styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
                                        backing: .buffered, defer: false)
        full.backgroundColor = .black
        full.isOpaque = true
        full.title = "SYN"
        full.titleVisibility = .hidden
        full.titlebarAppearsTransparent = true
        full.titlebarSeparatorStyle = .none
        for kind in [NSWindow.ButtonType.closeButton, .miniaturizeButton, .zoomButton] {
            full.standardWindowButton(kind)?.isHidden = true
        }
        // Native fullscreen ocupa su propio Space en el monitor correspondiente.
        full.level = .normal
        full.collectionBehavior = [.fullScreenPrimary, .fullScreenDisallowsTiling]
        full.delegate = full
        full.onFullscreenEntryFailure794 = { [weak self] in
            self?.synCompleteNativeFullscreenExit794()
        }
        full.onEscape = { [weak self] in
            guard let self else { return }
            if self.airPlayPanel797 != nil { self.stopAirPlay797(restoreVLC: true) }
            else if self.guidePanel70 != nil { self.closeGuide74() }
            else { self.exitFullscreen() }
        }
        full.onTogglePause = { [weak self] in self?.pauseOrResume() }
        full.onSeekBack = { [weak self] in self?.seekBackward() }
        full.onSeekForward = { [weak self] in self?.seekForward() }
        full.onSnapshot = { [weak self] in self?.snapshot() }
        let content = NSView(frame: NSRect(origin: .zero, size: screen.visibleFrame.size))
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.black.cgColor
        full.contentView = content
        // Transfer the ORIGINAL canvas. Never change player.drawable.
        NSLayoutConstraint.deactivate(canvasConstraints)
        canvas.removeFromSuperview()
        canvas.translatesAutoresizingMaskIntoConstraints = true
        canvas.frame = content.bounds
        canvas.autoresizingMask = [.width, .height]
        content.addSubview(canvas)
        let dim = SYNFullscreenUniformDim621(frame: content.bounds)
        dim.autoresizingMask = [.width, .height]
        dim.wantsLayer = true
        // SYN_622_DIM_35: tono NEGRO uniforme, 35 %, solo con controles visibles.
        dim.layer?.backgroundColor = NSColor.black.withAlphaComponent(0.35).cgColor
        dim.alphaValue = 0
        content.addSubview(dim)
        synUniformDim621 = dim
        bottomBar = makeBottomBar(in: content)
        topBar = makeTopBar(in: content)
        fullWindow = full
        // No modificar opciones globales de presentación en el fullscreen.
        // Starts entirely clean: HUD hidden, original video brightness.
        topBar?.alphaValue = 0
        bottomBar?.alphaValue = 0
        synUniformDim621?.alphaValue = 0
        synHUDIsVisible621 = false
        setCursorHidden(false)
        nativeEntering794 = true
        nativeExitRequested794 = false
        nativeMinimizeRequested794 = false
        nativeEnterObserver794 = NotificationCenter.default.addObserver(
            forName: NSWindow.didEnterFullScreenNotification, object: full, queue: .main
        ) { [weak self, weak full] _ in
            guard let self, let full, self.fullWindow === full else { return }
            self.nativeEntering794 = false
            if self.nativeExitRequested794 { full.toggleFullScreen(nil) }
        }
        nativeExitObserver794 = NotificationCenter.default.addObserver(
            forName: NSWindow.didExitFullScreenNotification, object: full, queue: .main
        ) { [weak self, weak full] _ in
            guard let self, let full, self.fullWindow === full else { return }
            self.synCompleteNativeFullscreenExit794()
        }
        full.makeKeyAndOrderFront(nil)
        content.layoutSubtreeIfNeeded()
        localMouseMonitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown]) { [weak self] event in
            guard let self, event.window === self.fullWindow,
                  let content = self.fullWindow?.contentView else { return event }
            let point = content.convert(event.locationInWindow, from: nil)
            // No interceptar botones SwiftUI del panel de AirPlay integrado.
            if self.airPlayPanel797 != nil { return event }
            if let guidePanel = self.guidePanel70,
               guidePanel.frame.contains(point) { return event }
            if self.synHUDIsVisible621,
               ((self.topBar?.frame.contains(point) ?? false) ||
                (self.bottomBar?.frame.contains(point) ?? false)) { return event }
            if self.clickOnFullscreenControl621(point, in: content) {
                return event // Click on a button or slider retains its normal action.
            }
            self.setFullscreenHUDVisible621(!self.synHUDIsVisible621)
            return nil // The click acts on HUD only, not on VLC.
        }
        tick70?.invalidate()
        tick70 = Timer.scheduledTimer(timeInterval: 1, target: self,
                                       selector: #selector(updateClock70), userInfo: nil, repeats: true)
        updateClock70()
        // Debe iniciarse tras hacer visible la ventana; sin manipular el Dock global.
        DispatchQueue.main.async { [weak self, weak full] in
            guard let self, let full, self.fullWindow === full else { return }
            full.toggleFullScreen(nil)
        }
    }
    func exitFullscreen() {
        guard let full = fullWindow else { return }
        if airPlayPanel797 != nil { stopAirPlay797(restoreVLC: true) }
        if full.styleMask.contains(.fullScreen) {
            guard !nativeExitRequested794 else { return }
            nativeExitRequested794 = true
            full.toggleFullScreen(nil)
            return // Restauramos el canvas cuando macOS termine la transición.
        }
        if nativeEntering794 {
            nativeExitRequested794 = true
            return
        }
        synCompleteNativeFullscreenExit794()
    }

    private func synCompleteNativeFullscreenExit794() {
        guard let full = fullWindow else { return }
        if airPlayPanel797 != nil { stopAirPlay797(restoreVLC: true) }
        if let observer = nativeEnterObserver794 {
            NotificationCenter.default.removeObserver(observer)
            nativeEnterObserver794 = nil
        }
        if let observer = nativeExitObserver794 {
            NotificationCenter.default.removeObserver(observer)
            nativeExitObserver794 = nil
        }
        hideJob?.cancel(); hideJob = nil
        if let monitor = localMouseMonitor { NSEvent.removeMonitor(monitor); localMouseMonitor = nil }
        setCursorHidden(false)
        // Remove canvas from fullscreen while it still exists, then restore it.
        canvas.removeFromSuperview()
        canvas.translatesAutoresizingMaskIntoConstraints = false
        canvas.autoresizingMask = []
        addSubview(canvas)
        installCanvasConstraints()
        synUniformDim621?.removeFromSuperview()
        synUniformDim621 = nil
        synHUDIsVisible621 = false
        tick70?.invalidate(); tick70 = nil
        guidePanel70?.removeFromSuperview(); guidePanel70 = nil
        recButton70 = nil; nowLabel70 = nil; nextLabel70 = nil
        timeLabel70 = nil; programProgress70 = nil; timeShiftSlider70 = nil
        bottomBar = nil
        topBar = nil
        fullscreenPauseButton = nil
        channelLabel = nil
        full.orderOut(nil)
        fullWindow = nil
        if nativeMinimizeRequested794 { originalWindow?.miniaturize(nil) }
        else { originalWindow?.makeKeyAndOrderFront(nil) }
        nativeMinimizeRequested794 = false
        nativeExitRequested794 = false
        nativeEntering794 = false
        originalWindow = nil
    }
    @objc private func fullscreenExit() { exitFullscreen() }
    @objc private func minimizeSYN() {
        nativeMinimizeRequested794 = true
        exitFullscreen()
    }
    func stop() {
        stopAirPlay797(restoreVLC: false)
        exitFullscreen()
        #if canImport(VLCKit)
        player.stop()
        #endif
        currentURL = nil
    }
    deinit {
        if let observer = nativeEnterObserver794 { NotificationCenter.default.removeObserver(observer) }
        if let observer = nativeExitObserver794 { NotificationCenter.default.removeObserver(observer) }
        if let monitor = localMouseMonitor { NSEvent.removeMonitor(monitor) }
        hideJob?.cancel()
        if cursorHidden { NSCursor.unhide() }
        #if canImport(VLCKit)
        player.stop()
        #endif
    }
}

private struct SYNVideoSurface: NSViewRepresentable {
    let host: SYNVideoHost
    let url: URL?
    let title: String
    let now: SYNProgram70
    let next: SYNProgram70
    let channels: [SYNGuideChannel70]
    let tune: (String) -> Void
    let refreshGuide: () -> Void
    let loadGuide: (String) async -> [SYNGuideProgramme74]
    func makeNSView(context: Context) -> SYNVideoHost { host }
    func updateNSView(_ view: SYNVideoHost, context: Context) {
        view.configureTitle(title)
        view.configurePrograms70(now: now, next: next)
        view.configureGuide70(channels: channels, tune: tune, refresh: refreshGuide, load: loadGuide)
        view.play(url)
    }
}

// Alpha 3.0: genuine embedded playback controls. Fullscreen keeps its independent AppKit HUD.
// SYN 5.1 — mini-player overlay, designed after the GTK playback HUD.
// Preserve SYNVideoHost and its fullscreen implementation above this view.
struct VLCPlayerView: View {
    let url: URL?
    let channelTitle: String
    var onPreviousChannel: (() -> Void)? = nil
    var onNextChannel: (() -> Void)? = nil
    var onOpenGuide: (() -> Void)? = nil
    var nowProgram70 = SYNProgram70(title: "", start: nil, end: nil)
    var nextProgram70 = SYNProgram70(title: "", start: nil, end: nil)
    var guideChannels70: [SYNGuideChannel70] = []
    var tune70: (String) -> Void = { _ in }
    var refreshGuide70: () -> Void = {}
    var loadGuide74: (String) async -> [SYNGuideProgramme74] = { _ in [] }

    init(url: URL?, channelTitle: String = "Televisión en directo",
         onPreviousChannel: (() -> Void)? = nil,
         onNextChannel: (() -> Void)? = nil,
         onOpenGuide: (() -> Void)? = nil,
         nowProgram70: SYNProgram70 = SYNProgram70(title: "", start: nil, end: nil),
         nextProgram70: SYNProgram70 = SYNProgram70(title: "", start: nil, end: nil),
         guideChannels70: [SYNGuideChannel70] = [],
         tune70: @escaping (String) -> Void = { _ in },
         refreshGuide70: @escaping () -> Void = {},
         loadGuide74: @escaping (String) async -> [SYNGuideProgramme74] = { _ in [] }) {
        self.url = url
        self.channelTitle = channelTitle
        self.onPreviousChannel = onPreviousChannel
        self.onNextChannel = onNextChannel
        self.onOpenGuide = onOpenGuide
        self.nowProgram70 = nowProgram70
        self.nextProgram70 = nextProgram70
        self.guideChannels70 = guideChannels70
        self.tune70 = tune70
        self.refreshGuide70 = refreshGuide70
        self.loadGuide74 = loadGuide74
    }

    @State private var host = SYNVideoHost(frame: .zero)
    @State private var volume = 80.0
    @State private var muted = false
    @State private var paused = false
    @State private var controlsVisible = false
    @State private var hideTask: Task<Void, Never>?
    @State private var miniRecording795 = false
    @State private var miniCanRecord795 = false
    @State private var miniResolution795 = "Resolución pendiente"

    private func updateMiniStatus795() {
        miniRecording795 = host.synMiniIsRecording795()
        miniCanRecord795 = host.synMiniCanRecord795()
        miniResolution795 = host.synMiniActualResolution795()
    }

    private var isActive: Bool { url != nil }

    private func revealControls() {
        guard isActive else { return }
        hideTask?.cancel()
        withAnimation(.easeInOut(duration: 0.20)) { controlsVisible = true }
        hideTask = Task { @MainActor in
            do { try await Task.sleep(for: .seconds(5)) }
            catch { return }
            guard !Task.isCancelled else { return }
            withAnimation(.easeInOut(duration: 0.32)) { controlsVisible = false }
        }
    }

    private func concealControls() {
        hideTask?.cancel()
        withAnimation(.easeInOut(duration: 0.26)) { controlsVisible = false }
    }

    private func tool(_ symbol: String, tip: String, action: @escaping () -> Void) -> some View {
        Button(action: { action(); revealControls() }) {
            Image(systemName: symbol)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 33, height: 33)
                .foregroundStyle(.white)
                .background(.white.opacity(0.095), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
        .help(tip)
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            Color.black
            SYNVideoSurface(host: host, url: url, title: channelTitle,
                            now: nowProgram70, next: nextProgram70,
                            channels: guideChannels70, tune: tune70, refreshGuide: refreshGuide70,
                            loadGuide: loadGuide74)

            if isActive {
                VStack(spacing: 0) {
                    Spacer(minLength: 0)
                    VStack(alignment: .leading, spacing: 9) {
                        HStack(alignment: .bottom) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(channelTitle)
                                    .font(.system(size: 13, weight: .semibold))
                                    .lineLimit(1)
                                Text("EN DIRECTO")
                                    .font(.system(size: 10, weight: .medium))
                                    .tracking(0.9)
                                    .foregroundStyle(.white.opacity(0.76))
                                Text(miniResolution795)
                                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                                    .foregroundStyle(.white.opacity(0.80))
                                    .help("Resolución efectiva de la señal decodificada por VLCKit")
                            }
                            Spacer(minLength: 8)
                            HStack(spacing: 5) {
                                Circle().fill(.red).frame(width: 6, height: 6)
                                Text("LIVE").font(.system(size: 10, weight: .bold))
                            }
                            .foregroundStyle(.white)
                        }
                        HStack(spacing: 7) {
                            tool(paused ? "play.fill" : "pause.fill", tip: paused ? "Reanudar" : "Pausar") {
                                host.pauseOrResume()
                                paused.toggle()
                            }
                            tool("gobackward.10", tip: "Retroceder 10 s (si se permite)") {
                                host.embeddedSeekBack()
                            }
                            tool("goforward.10", tip: "Avanzar 10 s (si se permite)") {
                                host.embeddedSeekForward()
                            }
                            // SYN_MINI_STATUS_795: REC of shared Xtream stream.
                            Button {
                                host.synMiniToggleRecording795()
                                updateMiniStatus795()
                                revealControls()
                            } label: {
                                Image(systemName: miniRecording795 ? "stop.circle.fill" : "record.circle")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(miniRecording795 ? Color.red : Color.white)
                                    .frame(width: 33, height: 33)
                                    .background(.white.opacity(0.095), in: RoundedRectangle(cornerRadius: 10))
                            }
                            .buttonStyle(.plain)
                            .disabled(!miniCanRecord795)
                            .help(miniRecording795 ? "Detener grabación" :
                                  (miniCanRecord795 ? "Grabar el canal actual (misma conexión)" :
                                   "REC disponible al conectar un directo Xtream compatible"))
                            tool("camera", tip: "Guardar captura") {
                                host.embeddedSnapshot()
                            }
                            tool(muted ? "speaker.slash.fill" : "speaker.wave.2.fill", tip: "Silenciar") {
                                muted.toggle()
                                host.embeddedSetMuted(muted)
                            }
                            Slider(value: $volume, in: 0...100)
                                .frame(width: 76)
                                .tint(.orange)
                                .onChange(of: volume) { _, value in
                                    if muted { muted = false; host.embeddedSetMuted(false) }
                                    host.setVolume(value)
                                    revealControls()
                                }
                                .help("Volumen")
                            Spacer(minLength: 0)
                            tool("arrow.up.left.and.arrow.down.right", tip: "Pantalla completa") {
                                host.toggleFullscreen()
                            }
                        }
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 17)
                    .padding(.top, 35)
                    .padding(.bottom, 13)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background {
                        LinearGradient(colors: [Color.black.opacity(0.0), Color.black.opacity(0.58), Color.black.opacity(0.88)], startPoint: .top, endPoint: .bottom)
                    }
                }
                .opacity(controlsVisible ? 1 : 0)
                .allowsHitTesting(controlsVisible)
                .accessibilityHidden(!controlsVisible)
            }
        }
        .contentShape(Rectangle())
        .onHover { inside in
            if inside { revealControls() } else { concealControls() }
        }
        .onContinuousHover { phase in
            if case .active = phase { revealControls() }
        }
        .onChange(of: url) { _, _ in
            paused = false
            concealControls()
            host.setVolume(volume)
        }
        .onAppear {
            host.setVolume(volume)
            host.onPreviousChannel = onPreviousChannel
            host.onNextChannel = onNextChannel
            host.onOpenGuide = onOpenGuide
        }
        .onChange(of: channelTitle) { _, _ in
            host.onPreviousChannel = onPreviousChannel
            host.onNextChannel = onNextChannel
            host.onOpenGuide = onOpenGuide
        }
        .onDisappear { hideTask?.cancel(); hideTask = nil }
        // SYN_MINI_WATCH_7951: no modificamos el .onAppear original.
        .onAppear { updateMiniStatus795() }
        .onReceive(Timer.publish(every: 1.5, on: .main, in: .common).autoconnect()) { _ in
            updateMiniStatus795()
        }
        .clipped()
    }
}
