import Darwin
import AppKit
import SwiftUI
#if canImport(VLCKit)
import VLCKit
#endif

// SYN_PLAYBACK_USER_AGENT_911: VLC y entradas directas. El pool upstream se gestiona por separado.
// No guarda credenciales. El motor DVR autónomo tiene su propia cabecera HTTP.
enum SYNPlaybackUserAgent911 {
    static let presetKey = "syn.native.vlc.userAgentPreset911"
    static let customKey = "syn.native.vlc.userAgentCustom911"
    static let vlcDefault = "VLC/3.0.21 LibVLC/3.0.21"

    static var current: String {
        let pref = UserDefaults.standard.string(forKey: presetKey) ?? "vlc"
        switch pref {
        case "safari":
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        case "chrome":
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        case "firefox":
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0"
        case "kodi":
            return "Kodi/21.0"
        case "custom":
            let userText = UserDefaults.standard.string(forKey: customKey) ?? ""
            let text = userText.trimmingCharacters(in: .whitespacesAndNewlines)
            // Evitar inyección de cabeceras y entradas excesivas en la línea HTTP.
            if !text.isEmpty && text.utf8.count <= 512 && !text.contains("\r") && !text.contains("\n") {
                return text
            }
            return vlcDefault
        default: return vlcDefault
        }
    }
}

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

// SYN_RECONNECT_112: overlay puramente visual. No arranca conexiones ni modifica el DVR.
private final class SYNReconnectDisplay112: ObservableObject {
    @Published var visible = false
    @Published var prolonged = false
}

// Nunca interceptar clics, HUD, fullscreen ni gestos sobre el vídeo.
private final class SYNReconnectHosting112: NSHostingView<SYNReconnectVisual112> {
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
}

private struct SYNReconnectVisual112: View {
    @ObservedObject var model: SYNReconnectDisplay112
    private let sand: [Color] = [
        Color(red: 0.99, green: 0.25, blue: 0.29),
        Color(red: 1.00, green: 0.69, blue: 0.20),
        Color(red: 0.99, green: 0.88, blue: 0.33),
        Color(red: 0.35, green: 0.90, blue: 0.51),
        Color(red: 0.24, green: 0.85, blue: 0.97),
        Color(red: 0.33, green: 0.47, blue: 0.99),
        Color(red: 0.90, green: 0.38, blue: 0.91)
    ]

    var body: some View {
        ZStack {
            if model.visible {
                Color.black.opacity(0.23)
                VStack(spacing: 19) {
                    ZStack {
                        Circle()
                            .fill(.ultraThinMaterial)
                        Circle().fill(
                            LinearGradient(colors: [
                                .white.opacity(0.34), .white.opacity(0.06),
                                Color(red: 0.06, green: 0.12, blue: 0.24).opacity(0.62)
                            ], startPoint: .topLeading, endPoint: .bottomTrailing)
                        )
                        TimelineView(.animation(minimumInterval: 1.0 / 15.0)) { timeline in
                            Canvas(opaque: false, rendersAsynchronously: true) { context, size in
                                let t = timeline.date.timeIntervalSinceReferenceDate
                                // Sedimentos de carta de ajuste en la base de la esfera.
                                for band in 0..<7 {
                                    let width = size.width / 7.0
                                    let x = CGFloat(band) * width
                                    let rect = CGRect(x: x, y: size.height * 0.73,
                                                      width: width + 0.7, height: size.height * 0.31)
                                    context.fill(Path(rect), with: .color(sand[band].opacity(0.53)))
                                }
                                // 72 granos deterministas: sin timers ni estado aleatorio.
                                for i in 0..<72 {
                                    let a = Double((i * 73 + 19) % 97) / 97.0
                                    let b = Double((i * 43 + 7) % 101) / 101.0
                                    let progress = (b + t * (0.17 + Double(i % 5) * 0.019))
                                        .truncatingRemainder(dividingBy: 1.0)
                                    let drift = sin(t * 0.83 + Double(i)) * 0.027
                                    let x = CGFloat(min(0.93, max(0.07, a + drift))) * size.width
                                    let y = CGFloat(progress) * size.height
                                    let diameter: CGFloat = 2.5 + CGFloat(i % 4) * 0.65
                                    let particle = CGRect(x: x, y: y, width: diameter, height: diameter)
                                    context.fill(Path(ellipseIn: particle),
                                                 with: .color(sand[i % sand.count].opacity(0.92)))
                                }
                            }
                        }
                        .clipShape(Circle())
                        Circle()
                            .strokeBorder(LinearGradient(colors: [
                                .white.opacity(0.86), .white.opacity(0.25),
                                .white.opacity(0.62)
                            ], startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 1.7)
                        Ellipse()
                            .fill(.white.opacity(0.20))
                            .frame(width: 77, height: 21)
                            .blur(radius: 9)
                            .rotationEffect(.degrees(-24))
                            .offset(x: -25, y: -43)
                    }
                    .frame(width: 150, height: 150)
                    .shadow(color: .black.opacity(0.40), radius: 24, y: 12)
                    VStack(spacing: 6) {
                        Text(model.prolonged ? "Señal interrumpida" : "Reconectando señal…")
                            .font(.system(size: 18, weight: .semibold, design: .rounded))
                            .foregroundStyle(.white)
                        Text(model.prolonged ? "El canal todavía no envía vídeo" :
                             "Esperando a que vuelva la imagen")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(.white.opacity(0.78))
                    }
                    .shadow(color: .black.opacity(0.6), radius: 8, y: 2)
                }
                .padding(24)
                .transition(.opacity)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .animation(.easeInOut(duration: 0.23), value: model.visible)
        .allowsHitTesting(false)
        .accessibilityHidden(!model.visible)
    }
}

// SYN_FULLSCREEN_RETURN_11231: el canvas VLCKit viaja al Space fullscreen.
// El reproductor embebido NO crea otro vídeo: solo informa y ofrece regresar.
private struct SYNFullscreenReturn1123: View {
    let animate: Bool
    let restore: () -> Void

    private let sand: [Color] = [
        Color(red: 0.98, green: 0.34, blue: 0.27),
        Color(red: 0.18, green: 0.84, blue: 0.44),
        Color(red: 0.24, green: 0.53, blue: 0.98),
        Color(red: 0.27, green: 0.89, blue: 0.94),
        Color(red: 0.96, green: 0.38, blue: 0.82),
        Color(red: 0.98, green: 0.84, blue: 0.22),
        Color.white.opacity(0.92)
    ]

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(red: 0.08, green: 0.11, blue: 0.15),
                         Color(red: 0.025, green: 0.035, blue: 0.055)],
                startPoint: .topLeading, endPoint: .bottomTrailing
            )
            VStack(spacing: 12) {
                TimelineView(.animation(minimumInterval: 1.0 / 24.0, paused: !animate)) { timeline in
                    let t = timeline.date.timeIntervalSinceReferenceDate
                    ZStack {
                        Circle()
                            .fill(
                                RadialGradient(colors: [
                                    .white.opacity(0.30),
                                    .white.opacity(0.11),
                                    Color.black.opacity(0.08)
                                ], center: .topLeading, startRadius: 8, endRadius: 84)
                            )
                        Circle()
                            .fill(.ultraThinMaterial)
                            .overlay {
                                Canvas { context, size in
                                    let liquidHeight = size.height * 0.34
                                    let liquidRect = CGRect(x: 0, y: size.height - liquidHeight, width: size.width, height: liquidHeight)
                                    context.fill(Path(ellipseIn: liquidRect.insetBy(dx: -6, dy: -4)),
                                                 with: .linearGradient(Gradient(colors: sand.map { $0.opacity(0.18) }),
                                                                       startPoint: CGPoint(x: 0, y: size.height - liquidHeight),
                                                                       endPoint: CGPoint(x: size.width, y: size.height)))
                                    for i in 0..<72 {
                                        let a = Double((i * 73 + 19) % 97) / 97.0
                                        let b = Double((i * 43 + 7) % 101) / 101.0
                                        let progress = (b + t * (0.17 + Double(i % 5) * 0.019))
                                            .truncatingRemainder(dividingBy: 1.0)
                                        let drift = sin(t * 0.83 + Double(i)) * 0.027
                                        let x = CGFloat(min(0.93, max(0.07, a + drift))) * size.width
                                        let y = CGFloat(progress) * size.height
                                        let diameter: CGFloat = 2.5 + CGFloat(i % 4) * 0.65
                                        let particle = CGRect(x: x, y: y, width: diameter, height: diameter)
                                        context.fill(Path(ellipseIn: particle),
                                                     with: .color(sand[i % sand.count].opacity(0.92)))
                                    }
                                }
                            }
                            .clipShape(Circle())
                        Circle()
                            .strokeBorder(LinearGradient(colors: [
                                .white.opacity(0.86), .white.opacity(0.25),
                                .white.opacity(0.62)
                            ], startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 1.7)
                        Ellipse()
                            .fill(.white.opacity(0.20))
                            .frame(width: 72, height: 20)
                            .blur(radius: 9)
                            .rotationEffect(.degrees(-24))
                            .offset(x: -23, y: -39)
                    }
                    .frame(width: 120, height: 120)
                    .shadow(color: .black.opacity(0.40), radius: 24, y: 12)
                }
                Text("La TV está en pantalla completa")
                    .font(.system(size: 16, weight: .semibold))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.white)
                Button(action: restore) {
                    Label("Volver a ventana", systemImage: "arrow.down.right.and.arrow.up.left")
                        .font(.system(size: 13, weight: .semibold))
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .tint(.orange)
                .padding(.top, 2)
                .help("Salir de la pantalla completa y recuperar el vídeo en SYN")
            }
            .padding(.horizontal, 29)
            .padding(.vertical, 25)
            .frame(maxWidth: 410)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .strokeBorder(.white.opacity(0.17), lineWidth: 1)
            }
            .padding(22)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

final class SYNVideoHost: NSView {
    private let canvas = NSView()
    private var canvasConstraints: [NSLayoutConstraint] = []
    private var currentURL: URL?
    private var fullWindow: SYNFullscreenWindow?
    private weak var originalWindow: NSWindow?
    // SYN_FULLSCREEN_RETURN_1123: panel interactivo solo en la ventana original.
    private var fullscreenReturn1123: NSHostingView<SYNFullscreenReturn1123>?
    // SYN_CPU_1126: no actualizar la esfera si el Space de la ventana original no es visible.
    private var fullscreenReturnSpaceObserver1126: NSObjectProtocol?
    private var fullscreenReturnOcclusionObserver1126: NSObjectProtocol?
    private var fullscreenReturnAnimating1126: Bool?
    private var topBar: NSView?
    private var bottomBar: NSView?
    private var localMouseMonitor: Any?
    private var cursorMovementMonitor1124: Any?
    private var cursorIdleJob1124: DispatchWorkItem?
    private var fullscreenDidBecomeKey1124: NSObjectProtocol?
    private var fullscreenDidResignKey1124: NSObjectProtocol?
    private var appDidResignActive1124: NSObjectProtocol?
    // SYN_FS_CLICK_1122: la TV fullscreen revela el HUD por clic, nunca por movimiento.
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
    // SYN_TV_FULLSCREEN_ZOOM_910: impedir la doble animacion y el HUD erratico.
    private var liveTransitioning910 = false
    private var liveHUDHoldUntil910: TimeInterval = 0
    var liveMiniHUDLocked910: Bool {
        liveTransitioning910 || fullWindow != nil || ProcessInfo.processInfo.systemUptime < liveHUDHoldUntil910
    }
    private var fullscreenPauseButton: NSButton?
    private var embeddedPauseButton: NSButton?
    private var pausedByUser = false
    private var volumeValue: Double = 80
    private var muted = false
    // SYN_RECORDING_IN_WINDOW_94: audio en directo silenciado en visor MKV.
    private var recordingPlaybackMuted94 = false
    func setRecordingPlaybackMuted94(_ active: Bool) {
        recordingPlaybackMuted94 = active
        #if canImport(VLCKit)
        player.audio?.volume = Int32(active || muted ? 0 : volumeValue)
        #endif
    }
    private var slider: NSSlider?
    private var channelLabel: NSTextField?
    // SYN_FS_CLICK_1122: clic para mostrar/ocultar, autoocultar tras 8 s sin interacción.
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
    var onScheduleGuide90: ((String, String, Date, Date) throws -> Void)?
    private var guidePanel70: NSView?
    // SYN_AIRPLAY_FULLSCREEN_797: AirPlay vive solo en el Space fullscreen.
    // El HLS local compartido sigue alimentando DVR; VLC deja de reproducir.
    private let airPlay797 = SYNAirPlayPlayback796()
    private var airPlayPanel797: NSView?
    private var liveSession70: SYNSharedLive70.Stream?
    private var loadSerial70 = 0
    // SYN_VLC_AUTONOMO_110: la URL del canal NO cambia al cerrar/abrir DVR.
    // Vigilamos la propiedad del flujo, no el estado de "playing" de VLC.
    private var routeWatch110: Timer?
    private var usingSharedPool110: Bool? = nil
    private var sharedPoolPort110: Int? = nil
    private var poolJoinInFlight110 = false
    private var lastPoolJoin110: TimeInterval = 0
    private var missingPoolPolls110 = 0
    // SYN_RECONNECT_112: únicamente monitoriza VLCKit; no hace reintentos ni retunes.
    private let reconnectDisplay112 = SYNReconnectDisplay112()
    private var reconnectHosting112: SYNReconnectHosting112?
    private var reconnectTimer112: Timer?
    private var reconnectSuspectedAt112: TimeInterval?
    private var reconnectRecoveredAt112: TimeInterval?
    private var reconnectShownAt112: TimeInterval?
    private var reconnectRouteChangedAt112 = ProcessInfo.processInfo.systemUptime
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
        configureReconnect112()
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

    // SYN_RECONNECT_112: el overlay es hijo del canvas; sigue al mismo vídeo
    // cuando el canvas se traslada a la ventana fullscreen de macOS.
    private func configureReconnect112() {
        let overlay = SYNReconnectHosting112(rootView: SYNReconnectVisual112(model: reconnectDisplay112))
        overlay.translatesAutoresizingMaskIntoConstraints = false
        overlay.wantsLayer = true
        overlay.layer?.zPosition = 10_000
        canvas.addSubview(overlay, positioned: .above, relativeTo: nil)
        NSLayoutConstraint.activate([
            overlay.leadingAnchor.constraint(equalTo: canvas.leadingAnchor),
            overlay.trailingAnchor.constraint(equalTo: canvas.trailingAnchor),
            overlay.topAnchor.constraint(equalTo: canvas.topAnchor),
            overlay.bottomAnchor.constraint(equalTo: canvas.bottomAnchor)
        ])
        reconnectHosting112 = overlay
        let timer = Timer(timeInterval: 0.5, repeats: true) { [weak self] _ in
            self?.inspectReconnect112()
        }
        reconnectTimer112 = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func resetReconnect112() {
        reconnectRouteChangedAt112 = ProcessInfo.processInfo.systemUptime
        reconnectSuspectedAt112 = nil
        reconnectRecoveredAt112 = nil
        reconnectShownAt112 = nil
        reconnectDisplay112.visible = false
        reconnectDisplay112.prolonged = false
    }

    // SYN_RECONNECT_1121: la esfera requiere indicios corroborados de corte.
    // "buffering" en VLCKit NO equivale necesariamente a vídeo detenido.
    // Se prioriza no dar falsos positivos, aunque se tarde en detectar cortes.
    private func inspectReconnect112() {
        #if canImport(VLCKit)
        // Nunca bloquear imagen válida por cambios de fuente, pausa, AirPlay o VOD.
        guard let url = currentURL,
              ["http", "https"].contains(url.scheme?.lowercased() ?? ""),
              !["mp4", "mkv", "avi", "mov", "m4v"].contains(url.pathExtension.lowercased()),
              !pausedByUser, airPlay797.player == nil, !replaying70,
              !liveTransitioning910, !poolJoinInFlight110 else {
            reconnectSuspectedAt112 = nil
            reconnectRecoveredAt112 = nil
            reconnectDisplay112.visible = false
            reconnectDisplay112.prolonged = false
            return
        }

        let now = ProcessInfo.processInfo.systemUptime
        guard now - reconnectRouteChangedAt112 >= 7.0 else { return }
        let state = player.state

        // Veto absoluto: si VLC dice que reproduce, NO tapar el vídeo.
        // Incluso si state == .buffering en un instante transitorio.
        if player.isPlaying || state == .playing {
            reconnectSuspectedAt112 = nil
            reconnectRecoveredAt112 = nil
            reconnectShownAt112 = nil
            reconnectDisplay112.visible = false
            reconnectDisplay112.prolonged = false
            return
        }

        let severe = state == .error || state == .ended || state == .stopped
        let waiting = state == .buffering || state == .opening

        // El HLS compartido dispone de una segunda prueba objetiva:
        // una lista m3u8 realmente estancada, no solo el estado de VLC.
        let confirmed: Bool
        if usingSharedPool110 == true {
            if let stream = liveSession70 {
                let attrs = try? FileManager.default.attributesOfItem(atPath: stream.playlist.path)
                if let modified = attrs?[.modificationDate] as? Date {
                    let age = Date().timeIntervalSince(modified)
                    // Evita falsos positivos con segmentos largos o escritura lenta.
                    confirmed = (severe || waiting) && age >= 18.0
                } else {
                    // La lista no existe pese a que el stream ya estaba preparado.
                    confirmed = severe || waiting
                }
            } else {
                // Aún se está preparando el pool: no mostrar aviso.
                confirmed = false
            }
        } else {
            // En IPTV directo no tenemos HLS local que corrobore el atasco.
            // No utilizar .buffering/.opening solos: algunos streams muestran
            // vídeo mientras VLCKit mantiene esos estados.
            confirmed = severe
        }

        if confirmed {
            reconnectRecoveredAt112 = nil
            if reconnectSuspectedAt112 == nil { reconnectSuspectedAt112 = now }
            // En directo, exigir un fallo duro prolongado. En HLS compartido,
            // la antigüedad >=18 s del manifiesto aporta la segunda confirmación.
            let threshold = usingSharedPool110 == true ? 5.0 : 12.0
            if now - (reconnectSuspectedAt112 ?? now) >= threshold {
                if !reconnectDisplay112.visible {
                    reconnectDisplay112.visible = true
                    reconnectShownAt112 = now
                    if let overlay = reconnectHosting112 {
                        canvas.addSubview(overlay, positioned: .above, relativeTo: nil)
                    }
                }
                reconnectDisplay112.prolonged = now - (reconnectShownAt112 ?? now) >= 11
            }
        } else {
            reconnectSuspectedAt112 = nil
            // Desaparece inmediatamente cuando vuelve el estado válido: nunca
            // mantener una pantalla de bloqueo sobre una imagen que funciona.
            reconnectRecoveredAt112 = nil
            reconnectShownAt112 = nil
            reconnectDisplay112.visible = false
            reconnectDisplay112.prolonged = false
        }
        #endif
    }

    // Un pool.port antiguo NO significa que el motor siga activo.
    // SYN_POOL_SEGURO_103: NO abrir un stream directo si el motor está vivo.
    // Un pool.status.json retrasado no implica que el motor haya terminado.
    private static func synPoolDisponible101() -> Bool {
        let base = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
        let heartbeat = base.appendingPathComponent("worker.heartbeat.json")
        if let data = try? Data(contentsOf: heartbeat),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let pidValue = object["pid"] as? NSNumber,
           pidValue.int32Value > 1 {
            // SYN_VLC_AUTONOMO_110: un heartbeat reciente en disco NO prueba
            // que el proceso siga vivo. Si murió, no usar su pool.port antiguo.
            return kill(pid_t(pidValue.int32Value), 0) == 0
        }
        // Durante el arranque también respetar el pool si su estado es reciente.
        let statusPath = base.appendingPathComponent("pool.status.json")
        guard let data = try? Data(contentsOf: statusPath),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let stamp = (object["timestamp"] as? NSNumber)?.doubleValue else { return false }
        let age = Date().timeIntervalSince1970 - stamp
        guard age >= -5 && age < 10,
              let raw = try? String(contentsOf: base.appendingPathComponent("pool.port"), encoding: .utf8),
              let port = Int(raw.trimmingCharacters(in: .whitespacesAndNewlines)),
              (1...65535).contains(port) else { return false }
        return true
    }

    // SYN_VLC_AUTONOMO_110: comprobar la ruta incluso cuando el mismo canal
    // permanece seleccionado. Es independiente del redibujado de SwiftUI.
    private static func poolPort110() -> Int? {
        let path = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/pool.port")
        guard let value = try? String(contentsOf: path, encoding: .utf8),
              let port = Int(value.trimmingCharacters(in: .whitespacesAndNewlines)),
              (1...65535).contains(port) else { return nil }
        return port
    }

    private func beginRouteWatch110() {
        guard routeWatch110 == nil else { return }
        let timer = Timer(timeInterval: 1.25, repeats: true) { [weak self] _ in
            self?.checkRoute110()
        }
        routeWatch110 = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func checkRoute110() {
        guard let url = currentURL, usingSharedPool110 != nil else { return }
        let engineAvailable = Self.synPoolDisponible101()
        if engineAvailable {
            missingPoolPolls110 = 0
            let newPort = Self.poolPort110()
            if usingSharedPool110 != true {
                // El DVR acaba de iniciarse: cerrar VLC directo antes de
                // solicitar el flujo local. Nunca mantener dos upstream.
                play(url, refreshRoute110: true)
                return
            }
            if let newPort, let oldPort = sharedPoolPort110, newPort != oldPort {
                // Reinicio del motor con otro puerto: descartar el HLS antiguo.
                SYNSharedLive70.shared.shutdown()
                play(url, refreshRoute110: true)
                return
            }
            if sharedPoolPort110 == nil { sharedPoolPort110 = newPort }
            // El motor puede tardar en crear pool.port o en servir el HLS.
            // Esperar a que termine el intento anterior para no multiplicar timers.
            if liveSession70 == nil && !poolJoinInFlight110 &&
                Date().timeIntervalSince1970 - lastPoolJoin110 >= 4 {
                play(url, refreshRoute110: true)
            }
        } else if usingSharedPool110 == true {
            // Dos observaciones para no reabrir el proveedor por una lectura
            // transitoria. El motor muerto no debe retener VLC en 127.0.0.1.
            missingPoolPolls110 += 1
            if missingPoolPolls110 >= 2 {
                missingPoolPolls110 = 0
                play(url, refreshRoute110: true)
            }
        } else {
            missingPoolPolls110 = 0
        }
    }

    // Exactly ONE provider media stream: FFmpeg ingests it; VLC plays local HLS.
    // Changing channels while REC is active keeps the previous local feed recording,
    // opening a second provider stream only for the *different* channel.
    func play(_ url: URL?, refreshRoute110: Bool = false) {
        guard currentURL != url || refreshRoute110 else { return }
        resetReconnect112()
        // Si cambiamos de canal durante AirPlay, limpiar la ruta externa antes
        // de sintonizar la siguiente fuente y sin reabrir el canal anterior.
        if airPlay797.player != nil { stopAirPlay797(restoreVLC: false) }
        currentURL = url
        loadSerial70 += 1
        let serial = loadSerial70
        liveSession70 = nil
        poolJoinInFlight110 = false
        replaying70 = false
        pausedByUser = false
        refreshPauseButtons()
        #if canImport(VLCKit)
        player.stop()
        #endif
        SYNSharedLive70.shared.releaseUnrecorded(except: url)
        guard let url else {
            usingSharedPool110 = nil
            sharedPoolPort110 = nil
            routeWatch110?.invalidate(); routeWatch110 = nil
            return
        }
        // SYN_VLC_AUTONOMO_110: directo con DVR cerrado, HLS compartido abierto.
        let isRemote = ["http", "https"].contains(url.scheme?.lowercased() ?? "")
        let isVOD = ["mp4", "mkv", "avi", "mov", "m4v"].contains(url.pathExtension.lowercased())
        if isRemote && !isVOD {
            beginRouteWatch110()
            let usePool = Self.synPoolDisponible101()
            usingSharedPool110 = usePool
            sharedPoolPort110 = usePool ? Self.poolPort110() : nil
            if !usePool {
                // Descarta viewer.json y sesiones HLS sin detener el DVR.
                SYNSharedLive70.shared.releaseUnrecorded(except: nil)
                playMedia70(url)
                return
            }
            poolJoinInFlight110 = true
            lastPoolJoin110 = Date().timeIntervalSince1970
            SYNSharedLive70.shared.session(for: url) { [weak self] session in
                guard let self, self.loadSerial70 == serial, self.currentURL == url else { return }
                self.poolJoinInFlight110 = false
                self.liveSession70 = session
                if let session { self.playMedia70(session.local) }
                // Si no está preparado, el monitor reintentará SIN abrir una
                // conexión directa mientras exista el motor compartido.
                else if !refreshRoute110 { NSSound.beep() }
                self.updateRecording70()
            }
        } else {
            usingSharedPool110 = nil
            sharedPoolPort110 = nil
            routeWatch110?.invalidate(); routeWatch110 = nil
            SYNSharedLive70.shared.releaseUnrecorded(except: nil)
            playMedia70(url)
        }
    }

    private func playMedia70(_ url: URL) {
        resetReconnect112()
        #if canImport(VLCKit)
        let media = VLCMedia(url: url)
        media.addOption(":http-user-agent=\(SYNPlaybackUserAgent911.current)")
        // Valores avanzados, conservadores por defecto; no tocan DVR ni la URL.
        let savedCache = UserDefaults.standard.integer(forKey: "syn.native.vlc.networkCaching799")
        let cacheMS = [500, 1000, 2000, 3000, 5000].contains(savedCache) ? savedCache : 1000
        media.addOption(":network-caching=\(cacheMS)")
        let hardware = UserDefaults.standard.string(forKey: "syn.native.vlc.hardware799") ?? "auto"
        if hardware == "none" { media.addOption(":avcodec-hw=none") }
        player.media = media
        player.play()
        player.audio?.volume = Int32(recordingPlaybackMuted94 || muted ? 0 : volumeValue)
        #endif
    }

    func pauseOrResume() {
        resetReconnect112()
        #if canImport(VLCKit)
        if player.isPlaying { player.pause(); pausedByUser = true }
        else { player.play(); pausedByUser = false }
        #endif
        refreshPauseButtons()
    }
    // Sincronizar el estado del mini con las acciones realizadas en fullscreen.
    func synMiniPlaybackPaused9101() -> Bool { pausedByUser }
    func synMiniPlaybackMuted9101() -> Bool { muted }
    private func refreshPauseButtons() {
        let symbol = pausedByUser ? "play.fill" : "pause.fill"
        fullscreenPauseButton?.image = NSImage(systemSymbolName: symbol, accessibilityDescription: "Reproducción o pausa")
    }
    func setVolume(_ value: Double) {
        volumeValue = max(0, min(value, 100))
        #if canImport(VLCKit)
        player.audio?.volume = Int32(recordingPlaybackMuted94 || muted ? 0 : volumeValue)
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
    // El minirreproductor usa saltos de 10 segundos: ofrecer los mismos en fullscreen.
    @objc private func synFullscreenBack10_9101() { seek(seconds: -10) }
    @objc private func synFullscreenForward10_9101() { seek(seconds: 10) }
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
        guard let url = currentURL, ["http", "https"].contains(url.scheme?.lowercased() ?? "") else {
            NSSound.beep(); return
        }
        do { _ = try SYNUnifiedDVR2.toggle(url: url, channel: channelTitle) }
        catch { NSAlert(error: error).runModal() }
        updateRecording70()
    }
    func synMiniCanRecord795() -> Bool { currentURL != nil }
    func synMiniIsRecording795() -> Bool { SYNUnifiedDVR2.isRecording(url: currentURL) }
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
        let active = SYNUnifiedDVR2.isRecording(url: currentURL)
        recButton70?.title = active ? "■ REC" : "● REC"
        recButton70?.contentTintColor = active ? .systemRed : .white
        recButton70?.toolTip = active ? "Detener grabación autónoma del canal actual" : "Grabar con SYN DVR Engine 2.0"
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

        let back = button("gobackward.10", tip: "Retroceder 10 s (igual que en mini)", action: #selector(synFullscreenBack10_9101))
        let pause = button("pause.fill", tip: "Pausar/reanudar", action: #selector(pauseClicked))
        fullscreenPauseButton = pause
        let forward = button("goforward.10", tip: "Avanzar 10 s (igual que en mini)", action: #selector(synFullscreenForward10_9101))
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
                          load: @escaping (String) async -> [SYNGuideProgramme74],
                          schedule: @escaping (String, String, Date, Date) throws -> Void) {
        onScheduleGuide90 = schedule
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
                }, schedule: { [weak self] id, title, start, end in
                    guard let action = self?.onScheduleGuide90 else { return }
                    try action(id, title, start, end)
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
            }, schedule: { [weak self] id, title, start, end in
                guard let action = self?.onScheduleGuide90 else { return }
                try action(id, title, start, end)
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

    // SYN_FULLSCREEN_CURSOR_11241: ajuste persistente en Ajustes > Reproductor.
    // Default ON si el usuario todavía no ha elegido una preferencia.
    private var autoHideCursor11241: Bool {
        (UserDefaults.standard.object(forKey: "syn.native.fullscreenHideCursor11241") as? Bool) ?? true
    }

    // SYN_FULLSCREEN_CURSOR_1124: el HUD y el cursor tienen dos relojes INDEPENDIENTES.
    // Ratón en movimiento: solo recupera el cursor, NUNCA muestra/oscurece el HUD.
    private func resetCursorIdle1124() {
        cursorIdleJob1124?.cancel()
        cursorIdleJob1124 = nil
        setCursorHidden(false)
        guard autoHideCursor11241,
              let full = fullWindow, full.styleMask.contains(.fullScreen),
              !liveTransitioning910, full.isKeyWindow, NSApp.isActive else { return }
        let work = DispatchWorkItem { [weak self, weak full] in
            guard let self, let full, self.fullWindow === full,
                  self.autoHideCursor11241,
                  !self.liveTransitioning910, full.styleMask.contains(.fullScreen),
                  full.isKeyWindow, NSApp.isActive,
                  full.frame.contains(NSEvent.mouseLocation) else { return }
            self.cursorIdleJob1124 = nil
            self.setCursorHidden(true)
        }
        cursorIdleJob1124 = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 15, execute: work)
    }

    private func stopCursorIdle1124() {
        cursorIdleJob1124?.cancel()
        cursorIdleJob1124 = nil
        setCursorHidden(false)
    }

    // Both bars and the uniform black dim appear/disappear on video click ONLY.
    private func setFullscreenHUDVisible621(_ visible: Bool) {
        guard fullWindow != nil, !liveTransitioning910 else { return }
        synHUDIsVisible621 = visible
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.23
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            topBar?.animator().alphaValue = visible ? 1 : 0
            bottomBar?.animator().alphaValue = visible ? 1 : 0
            synUniformDim621?.animator().alphaValue = visible ? 1 : 0
        }
    }

    // SYN_FS_CLICK_1122: solo un clic sobre el video revela el HUD.
    // Pulsar un control del HUD reinicia los 8 s; mover el cursor no lo modifica.
    private func revealFullscreenControls9101() {
        guard let full = fullWindow, full.styleMask.contains(.fullScreen),
              !liveTransitioning910, guidePanel70 == nil, airPlayPanel797 == nil else { return }
        hideJob?.cancel()
        if !synHUDIsVisible621 { setFullscreenHUDVisible621(true) }
        let hide = DispatchWorkItem { [weak self, weak full] in
            guard let self, let full, self.fullWindow === full,
                  !self.liveTransitioning910, self.synHUDIsVisible621,
                  self.guidePanel70 == nil, self.airPlayPanel797 == nil else { return }
            self.hideJob = nil
            self.setFullscreenHUDVisible621(false)
        }
        hideJob = hide
        DispatchQueue.main.asyncAfter(deadline: .now() + 8, execute: hide)
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

    // SYN_CPU_1126: nunca renderizar 24 FPS en otro Space. La ventana mantiene
    // su esfera animada al regresar a ella, sin duplicar el reproductor VLC.
    private func updateFullscreenReturn1126() {
        guard let panel = fullscreenReturn1123, let original = originalWindow else { return }
        let shouldAnimate = original.isOnActiveSpace && original.occlusionState.contains(.visible)
        guard fullscreenReturnAnimating1126 != shouldAnimate else { return }
        fullscreenReturnAnimating1126 = shouldAnimate
        panel.rootView = SYNFullscreenReturn1123(animate: shouldAnimate,
                                                  restore: { [weak self] in self?.exitFullscreen() })
    }

    // La vista original muestra una salida útil, nunca una segunda instancia de VLC.
    private func showFullscreenReturn1123() {
        guard fullscreenReturn1123 == nil else { return }
        let panel = NSHostingView(rootView: SYNFullscreenReturn1123(
            animate: false, restore: { [weak self] in self?.exitFullscreen() }
        ))
        panel.frame = bounds
        panel.autoresizingMask = [.width, .height]
        addSubview(panel, positioned: .above, relativeTo: nil)
        fullscreenReturn1123 = panel
        fullscreenReturnAnimating1126 = false
        // activeSpaceDidChangeNotification no requiere sondeo ni temporizador.
        fullscreenReturnSpaceObserver1126 = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.activeSpaceDidChangeNotification,
            object: nil, queue: .main
        ) { [weak self] _ in self?.updateFullscreenReturn1126() }
        fullscreenReturnOcclusionObserver1126 = NotificationCenter.default.addObserver(
            forName: NSWindow.didChangeOcclusionStateNotification,
            object: originalWindow, queue: .main
        ) { [weak self] _ in self?.updateFullscreenReturn1126() }
        updateFullscreenReturn1126()
    }

    private func removeFullscreenReturn1123() {
        if let observer = fullscreenReturnSpaceObserver1126 {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
            fullscreenReturnSpaceObserver1126 = nil
        }
        if let observer = fullscreenReturnOcclusionObserver1126 {
            NotificationCenter.default.removeObserver(observer)
            fullscreenReturnOcclusionObserver1126 = nil
        }
        fullscreenReturnAnimating1126 = nil
        fullscreenReturn1123?.removeFromSuperview()
        fullscreenReturn1123 = nil
    }

    func toggleFullscreen() {
        guard !liveTransitioning910 else { return }
        if fullWindow != nil { exitFullscreen() } else { enterFullscreen() }
    }
    private func enterFullscreen() {
        guard fullWindow == nil,
              let sourceWindow = window,
              let screen = sourceWindow.screen ?? NSScreen.main else { return }
        originalWindow = sourceWindow
        liveTransitioning910 = true
        // SYN_TV_FULLSCREEN_ZOOM_910: la ventana nace donde esta el minirreproductor,
        // NO ocupando ya el monitor. macOS hace el unico zoom al crear el Space.
        let videoRect = sourceWindow.convertToScreen(convert(bounds, to: nil))
        let initialRect: NSRect
        if videoRect.width > 80 && videoRect.height > 45 {
            initialRect = videoRect
        } else {
            initialRect = NSRect(x: screen.visibleFrame.midX - 320,
                                 y: screen.visibleFrame.midY - 180,
                                 width: 640, height: 360)
        }
        // La ventana con título (oculto) permite activar el fullscreen NATIVO.
        // Con .borderless macOS no crea un Space fullscreen ni oculta su propia barra.
        let full = SYNFullscreenWindow(contentRect: initialRect,
                                        styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
                                        backing: .buffered, defer: false)
        full.backgroundColor = .black
        full.isOpaque = true
        full.title = "SYN"
        // Se necesitan eventos de movimiento para despertar el cursor (no el HUD).
        full.acceptsMouseMovedEvents = true // SYN_FULLSCREEN_CURSOR_1124
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
        let content = NSView(frame: NSRect(origin: .zero, size: initialRect.size))
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
        // El hueco original ahora ofrece "Volver a ventana" sin otro drawable.
        showFullscreenReturn1123()
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
            self.liveTransitioning910 = false
            self.resetCursorIdle1124() // comienza el plazo de 15 s al entrar al Space.
            if self.nativeExitRequested794 {
                self.liveTransitioning910 = true
                full.toggleFullScreen(nil)
            }
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
            // Ignorar pulsaciones mientras macOS anima el Space.
            if self.liveTransitioning910 { return event }
            self.resetCursorIdle1124() // el clic reinicia 15 s, aparte de los 8 s del HUD.
            let point = content.convert(event.locationInWindow, from: nil)
            // No interceptar botones SwiftUI del panel de AirPlay integrado.
            if self.airPlayPanel797 != nil { return event }
            if let guidePanel = self.guidePanel70,
               guidePanel.frame.contains(point) { return event }
            if self.synHUDIsVisible621,
               ((self.topBar?.frame.contains(point) ?? false) ||
                (self.bottomBar?.frame.contains(point) ?? false)) {
                self.revealFullscreenControls9101() // 8 s desde la última interacción.
                return event // La pulsación sobre el HUD llega a sus controles.
            }
            if self.clickOnFullscreenControl621(point, in: content) {
                self.revealFullscreenControls9101()
                return event // Los botones y sliders conservan sus acciones.
            }
            if self.synHUDIsVisible621 {
                self.hideJob?.cancel()
                self.hideJob = nil
                self.setFullscreenHUDVisible621(false)
            } else {
                self.revealFullscreenControls9101()
            }
            return nil // The click acts on HUD only, not on VLC.
        }
        // SYN_FULLSCREEN_CURSOR_1124: el movimiento solo reactiva el CURSOR.
        // Nunca llama a revealFullscreenControls9101 ni cambia el atenuado.
        cursorMovementMonitor1124 = NSEvent.addLocalMonitorForEvents(
            matching: [.mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged]
        ) { [weak self, weak full] event in
            guard let self, let full, self.fullWindow === full,
                  event.window === full, !self.liveTransitioning910 else { return event }
            self.resetCursorIdle1124()
            return event
        }
        // No ocultar globalmente el puntero al salir del Space o de la aplicación.
        fullscreenDidResignKey1124 = NotificationCenter.default.addObserver(
            forName: NSWindow.didResignKeyNotification, object: full, queue: .main
        ) { [weak self] _ in self?.stopCursorIdle1124() }
        fullscreenDidBecomeKey1124 = NotificationCenter.default.addObserver(
            forName: NSWindow.didBecomeKeyNotification, object: full, queue: .main
        ) { [weak self] _ in self?.resetCursorIdle1124() }
        appDidResignActive1124 = NotificationCenter.default.addObserver(
            forName: NSApplication.didResignActiveNotification, object: nil, queue: .main
        ) { [weak self] _ in self?.stopCursorIdle1124() }
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
            liveTransitioning910 = true
            nativeExitRequested794 = true
            full.toggleFullScreen(nil)
            return // Restauramos el canvas cuando macOS termine la transición.
        }
        if nativeEntering794 {
            nativeExitRequested794 = true
            return
        }
        liveTransitioning910 = true
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
        if let monitor = cursorMovementMonitor1124 { NSEvent.removeMonitor(monitor); cursorMovementMonitor1124 = nil }
        for observer in [fullscreenDidBecomeKey1124, fullscreenDidResignKey1124, appDidResignActive1124] {
            if let observer { NotificationCenter.default.removeObserver(observer) }
        }
        fullscreenDidBecomeKey1124 = nil
        fullscreenDidResignKey1124 = nil
        appDidResignActive1124 = nil
        stopCursorIdle1124()
        // Retirar el panel antes de devolver el ÚNICO canvas de VLC.
        removeFullscreenReturn1123()
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
        liveTransitioning910 = false
        liveHUDHoldUntil910 = ProcessInfo.processInfo.systemUptime + 0.45
        originalWindow = nil
    }
    @objc private func fullscreenExit() { exitFullscreen() }
    @objc private func minimizeSYN() {
        nativeMinimizeRequested794 = true
        exitFullscreen()
    }
    func stop() {
        resetReconnect112()
        stopAirPlay797(restoreVLC: false)
        exitFullscreen()
        #if canImport(VLCKit)
        player.stop()
        #endif
        currentURL = nil
        usingSharedPool110 = nil
        sharedPoolPort110 = nil
        poolJoinInFlight110 = false
        routeWatch110?.invalidate(); routeWatch110 = nil
        SYNSharedLive70.shared.releaseUnrecorded(except: nil)
    }
    deinit {
        reconnectTimer112?.invalidate()
        routeWatch110?.invalidate()
        if let observer = nativeEnterObserver794 { NotificationCenter.default.removeObserver(observer) }
        if let observer = nativeExitObserver794 { NotificationCenter.default.removeObserver(observer) }
        if let monitor = localMouseMonitor { NSEvent.removeMonitor(monitor) }
        if let monitor = cursorMovementMonitor1124 { NSEvent.removeMonitor(monitor) }
        for observer in [fullscreenDidBecomeKey1124, fullscreenDidResignKey1124, appDidResignActive1124] {
            if let observer { NotificationCenter.default.removeObserver(observer) }
        }
        cursorIdleJob1124?.cancel()
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
    let scheduleGuide: (String, String, Date, Date) throws -> Void
    func makeNSView(context: Context) -> SYNVideoHost { host }
    func updateNSView(_ view: SYNVideoHost, context: Context) {
        view.configureTitle(title)
        view.configurePrograms70(now: now, next: next)
        view.configureGuide70(channels: channels, tune: tune, refresh: refreshGuide, load: loadGuide,
            schedule: scheduleGuide)
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
    var scheduleGuide70: (String, String, Date, Date) throws -> Void = { _, _, _, _ in }

    init(url: URL?, channelTitle: String = "Televisión en directo",
         onPreviousChannel: (() -> Void)? = nil,
         onNextChannel: (() -> Void)? = nil,
         onOpenGuide: (() -> Void)? = nil,
         nowProgram70: SYNProgram70 = SYNProgram70(title: "", start: nil, end: nil),
         nextProgram70: SYNProgram70 = SYNProgram70(title: "", start: nil, end: nil),
         guideChannels70: [SYNGuideChannel70] = [],
         tune70: @escaping (String) -> Void = { _ in },
         refreshGuide70: @escaping () -> Void = {},
         loadGuide74: @escaping (String) async -> [SYNGuideProgramme74] = { _ in [] },
         scheduleGuide70: @escaping (String, String, Date, Date) throws -> Void = { _, _, _, _ in }) {
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
        self.scheduleGuide70 = scheduleGuide70
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
        paused = host.synMiniPlaybackPaused9101()
        muted = host.synMiniPlaybackMuted9101()
    }

    private var isActive: Bool { url != nil }

    private func revealControls() {
        guard isActive, !host.liveMiniHUDLocked910 else { return }
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
                            loadGuide: loadGuide74, scheduleGuide: scheduleGuide70)

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
                                concealControls()
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
            // SYN_RECORDING_IN_WINDOW_94: no alterar FFmpeg ni liberar conexiones.
        .onReceive(NotificationCenter.default.publisher(for: .synRecordingPlayback94Changed)) { event in
            host.setRecordingPlaybackMuted94(event.userInfo?["active"] as? Bool ?? false)
        }
}
}
