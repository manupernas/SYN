import AppKit
import SwiftUI
import UserNotifications

// SYN_DVR_DASHBOARD_322 — fixed popover content height, no recording engine changes.
@main
@MainActor
struct SYNDVRMenuApp: App {
    @StateObject private var dvr = SYNDVRMenuModel()
    @NSApplicationDelegateAdaptor(SYNStandaloneAppDelegate42.self) private var appDelegate

    var body: some Scene {
        MenuBarExtra {
            DVRDashboard(dvr:dvr).environmentObject(SYNStandaloneController42.shared)
        } label: {
            if dvr.isRecording {
                Image(systemName:"record.circle.fill")
                    .foregroundStyle(.red)
                    .help("SYN DVR · \(dvr.active.count) tarea(s) activas")
            } else if dvr.isReconnecting {
                Image(systemName:"arrow.clockwise.circle.fill")
                    .foregroundStyle(.orange)
                    .help("SYN DVR · Recuperando señal")
            } else {
                Image(systemName:"record.circle")
                    .help(dvr.workerOnline ? "SYN DVR · Listo" : "SYN DVR · Motor desconectado")
            }
        }
        .menuBarExtraStyle(.window)
    }
}

// SYN_DVR_POPUP_GLASS_441 — solo apariencia del panel de MenuBarExtra.
// Sin cambios en modelo, controles, scroll, motor ni acciones de grabación.
private struct SYNDVRPopupGlass441: ViewModifier {
    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(macOS 26.0, *) {
            content.glassEffect(.regular, in: .rect(cornerRadius: 18))
        } else {
            content.background(.ultraThinMaterial,
                               in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
    }
}

// SYN_DVR_NOSCROLLER_433 — la lista DVR ya NO usa el ScrollView de SwiftUI:
// NSScrollView sin scrollers nativos + indicador 3x32 transitorio.
// El documento SwiftUI sigue actualizándose con los estados del menú.
private struct SYNDVRNoScroller433<Content: View>: NSViewRepresentable {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }

    func makeNSView(context: Context) -> SYNDVRPanelScroll433 {
        let scroll = SYNDVRPanelScroll433(frame: .zero)
        let host = NSHostingView(rootView: content)
        host.sizingOptions = [.intrinsicContentSize]
        host.translatesAutoresizingMaskIntoConstraints = false
        scroll.documentView = host
        NSLayoutConstraint.activate([
            host.leadingAnchor.constraint(equalTo: scroll.contentView.leadingAnchor),
            host.topAnchor.constraint(equalTo: scroll.contentView.topAnchor),
            host.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor)
        ])
        scroll.configureThumb433()
        return scroll
    }

    func updateNSView(_ scroll: SYNDVRPanelScroll433, context: Context) {
        if let host = scroll.documentView as? NSHostingView<Content> {
            host.rootView = content
            host.invalidateIntrinsicContentSize()
        }
        scroll.hasVerticalScroller = false
        scroll.hasHorizontalScroller = false
        // SYN_DVR_HEADER_442: evita conservar un desplazamiento inicial fantasma.
        // Si la persona ha desplazado la lista, se conserva su posicion.
        scroll.restoreInitialTop442()
        scroll.refreshThumb433()
    }
}

private final class SYNDVRScrollThumb433: NSView {
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
}

private final class SYNDVRPanelScroll433: NSScrollView {
    private let synThumb433 = SYNDVRScrollThumb433(frame:.zero)
    private var hideTask433: DispatchWorkItem?
    // No confundir cambios de tamano del documento con scroll hecho por el usuario.
    private var userScrolled442 = false
    private var restoringTop442 = false

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        configure433()
    }
    required init?(coder: NSCoder) {
        super.init(coder: coder)
        configure433()
    }
    private func configure433() {
        hasVerticalScroller = false
        hasHorizontalScroller = false
        autohidesScrollers = true
        drawsBackground = false
        borderType = .noBorder
        contentView.postsBoundsChangedNotifications = true
        NotificationCenter.default.addObserver(self,
            selector: #selector(scrollDidMove433(_:)),
            name: NSView.boundsDidChangeNotification, object: contentView)
        synThumb433.wantsLayer = true
        synThumb433.layer?.backgroundColor = NSColor.labelColor.withAlphaComponent(0.48).cgColor
        synThumb433.layer?.cornerRadius = 1.5
        synThumb433.isHidden = true
        addSubview(synThumb433, positioned: .above, relativeTo: nil)
    }
    deinit {
        NotificationCenter.default.removeObserver(self)
        hideTask433?.cancel()
    }
    override func layout() {
        super.layout()
        // Ningún layout posterior de SwiftUI puede reactivar la barra nativa.
        if hasVerticalScroller { hasVerticalScroller = false }
        if hasHorizontalScroller { hasHorizontalScroller = false }
        refreshThumb433()
    }
    func configureThumb433() { refreshThumb433() }
    override func scrollWheel(with event: NSEvent) {
        if abs(event.scrollingDeltaY) > 0.1 { userScrolled442 = true }
        super.scrollWheel(with: event)
    }
    func restoreInitialTop442() {
        guard !userScrolled442, !restoringTop442,
              let document = documentView, contentView.bounds.height > 1 else { return }
        // NSHostingView puede utilizar coordenadas invertidas (flipped).
        // La posicion inicial depende de esa orientacion, no del alto del popup.
        let docBounds = document.bounds
        let topY = document.isFlipped
            ? docBounds.minY
            : max(docBounds.minY, docBounds.maxY - contentView.bounds.height)
        if abs(contentView.bounds.minY - topY) > 0.5 {
            restoringTop442 = true
            contentView.scroll(to: NSPoint(x: contentView.bounds.minX, y: topY))
            reflectScrolledClipView(contentView)
            restoringTop442 = false
        }
    }
    func refreshThumb433() {
        let visibleHeight = contentView.bounds.height
        let documentHeight = documentView?.fittingSize.height ?? 0
        let overflow = max(0, documentHeight - visibleHeight)
        if overflow < 2 || visibleHeight < 32 {
            synThumb433.isHidden = true
            return
        }
        let thumbHeight: CGFloat = 32
        let available = max(0, bounds.height - thumbHeight - 10)
        let fraction = min(1, max(0, contentView.bounds.minY / max(1, overflow)))
        let fromTop = 5 + fraction * available
        // El NSScrollView es no-flipped: invertir Y para posicionar la cápsula.
        let y = bounds.height - thumbHeight - fromTop
        synThumb433.frame = NSRect(x: bounds.width - 6, y: y, width: 3, height: thumbHeight)
    }
    @objc private func scrollDidMove433(_ notification: Notification) {
        guard window != nil, !restoringTop442 else { return }
        refreshThumb433()
        if (documentView?.fittingSize.height ?? 0) <= contentView.bounds.height + 2 { return }
        synThumb433.isHidden = false
        synThumb433.layer?.removeAllAnimations()
        synThumb433.alphaValue = 1
        hideTask433?.cancel()
        let work = DispatchWorkItem { [weak self] in
            guard let self else { return }
            NSAnimationContext.runAnimationGroup { ctx in
                ctx.duration = 0.22
                self.synThumb433.animator().alphaValue = 0
            } completionHandler: {
                self.synThumb433.isHidden = true
                self.synThumb433.alphaValue = 1
            }
        }
        hideTask433 = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0, execute: work)
    }
}

// SYN_DVR_REDESIGN_440 — ficha clara, controles visibles y anuncios opcionales.
// Mantiene sin cambios el NSScrollView 4.3.3 que elimina la barra gigante.
private struct DVRDashboard: View {
    @ObservedObject var dvr: SYNDVRMenuModel
    @EnvironmentObject private var synStandalone42: SYNStandaloneController42
    @ObservedObject private var synNotifications42 = SYNRecordingNotifier42.shared
    @AppStorage("syn.dvr.commercials.enabled") private var adsEnabled = false
    @State private var tab = 0
    @State private var connections = 1
    @State private var showMissing = false
    @State private var showAdHelp = false
    @State private var synUA43SheetOpen = false
    @State private var synServerSettingsOpen40 = false
    @State private var synStopConfirmation42 = false
    @State private var synQuitConfirmation42 = false

    private var available: [MenuDVRJob] { dvr.recent.filter { $0.fileAvailable } }
    private var missing: [MenuDVRJob] { dvr.recent.filter { !$0.fileAvailable } }
    private var panelHeight: CGFloat { tab == 2 ? 325 : 355 }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(alignment: .center, spacing: 11) {
                Image(systemName: "record.circle.fill")
                    .font(.system(size: 27, weight: .medium))
                    .foregroundStyle(dvr.isRecording ? Color.red : Color.accentColor)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(alignment: .firstTextBaseline, spacing: 7) {
                        Text("SYN DVR").font(.system(size: 19, weight: .bold))
                        Text("4.5.6 prueba").font(.system(size: 11, weight: .medium))
                            .foregroundStyle(.secondary)
                    }
                    Text(dvr.workerOnline ? (dvr.isRecording ? "Grabando en directo" : "Preparado para grabar") : "Motor desconectado")
                        .font(.system(size: 12))
                        .foregroundStyle(dvr.workerOnline ? Color.primary : Color.orange)
                }
                Spacer(minLength: 4)
                VStack(alignment: .trailing, spacing: 3) {
                    HStack(spacing: 5) {
                        Circle().fill(dvr.workerOnline ? Color.green : Color.orange)
                            .frame(width: 8, height: 8)
                        Text("\(dvr.occupied) / \(dvr.capacity)")
                            .font(.system(size: 12, weight: .semibold, design: .rounded))
                            .monospacedDigit()
                    }
                    Text("conexiones").font(.system(size: 10)).foregroundStyle(.secondary)
                }
            }
            HStack(spacing: 8) {
                statPill("En curso", count: dvr.active.count, icon: "record.circle", tint: .red)
                statPill("Pendientes", count: dvr.upcoming.count, icon: "calendar", tint: .orange)
                statPill("Guardadas", count: available.count, icon: "externaldrive", tint: .green)
            }
            Picker("Sección de SYN DVR", selection: $tab) {
                Text("Ahora").tag(0)
                Text("Grabaciones").tag(1)
                Text("Ajustes").tag(2)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .accessibilityLabel("Secciones de SYN DVR")

            if !dvr.workerOnline {
                Label("El motor no responde. Las programaciones se conservan.", systemImage: "exclamationmark.triangle.fill")
                    .font(.system(size: 12))
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }

            SYNDVRNoScroller433 {
                VStack(alignment: .leading, spacing: 14) {
                    if tab == 0 { nowContent }
                    else if tab == 1 { libraryContent }
                    else { settingsContent }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                // El primer titulo nunca debe tocar el borde recortado del NSClipView.
                .padding(.top, 12)
                .padding(.trailing, 7)
                .fixedSize(horizontal: false, vertical: true)
            }
            .frame(height: panelHeight)

            if !dvr.message.isEmpty {
                Label(dvr.message, systemImage: "info.circle")
                    .font(.system(size: 11))
                    .foregroundStyle(.primary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(9)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.accentColor.opacity(0.11), in: RoundedRectangle(cornerRadius: 8))
            }
            Divider()
            HStack(spacing: 8) {
                Button { dvr.openRecordings() } label: {
                    Label("Carpeta", systemImage: "folder")
                }
                Button { dvr.openSYN() } label: {
                    Label("Abrir SYN", systemImage: "play.rectangle")
                }
                Spacer()
                Button { dvr.refresh() } label: {
                    Image(systemName: "arrow.clockwise").frame(width: 17)
                }
                .help("Actualizar historial y comprobar archivos")
                .accessibilityLabel("Actualizar")
                Button {
                    if synStandalone42.running && !dvr.active.isEmpty { synQuitConfirmation42 = true }
                    else { NSApp.terminate(nil) }
                } label: {
                    Image(systemName: "power").frame(width: 17)
                }
                .help("Cerrar SYN DVR (también detiene el motor autónomo)")
                .accessibilityLabel("Cerrar SYN DVR")
            }
            .buttonStyle(.bordered)
            .controlSize(.regular)
        }
        .padding(17)
        .frame(width: 430)
        .modifier(SYNDVRPopupGlass441())
        .onAppear { dvr.refresh(); connections = dvr.capacity }
        .sheet(isPresented: $synUA43SheetOpen) { SYNRecorderUA43Settings() }
        .sheet(isPresented: $synServerSettingsOpen40) { SYNRemoteServerSettings40() }
        .confirmationDialog("¿Detener servidor y grabaciones?", isPresented: $synStopConfirmation42) {
            Button("Detener y cortar grabaciones", role: .destructive) { synStandalone42.stop() }
            Button("Cancelar", role: .cancel) { }
        } message: {
            Text("Las grabaciones activas se interrumpirán; las programadas se conservan.")
        }
        .confirmationDialog("¿Cerrar SYN DVR?", isPresented: $synQuitConfirmation42) {
            Button("Cerrar y detener grabaciones", role: .destructive) { NSApp.terminate(nil) }
            Button("Cancelar", role: .cancel) { }
        } message: {
            Text("Cerrar también detendrá el servidor y las grabaciones activas.")
        }
    }

    private func statPill(_ label: String, count: Int, icon: String, tint: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon).foregroundStyle(tint)
            Text("\(count)").fontWeight(.bold).monospacedDigit()
            Text(label).foregroundStyle(.secondary)
        }
        .font(.system(size: 11))
        .frame(maxWidth: .infinity)
        .padding(.vertical, 9)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.32), in: RoundedRectangle(cornerRadius: 10))
        .accessibilityElement(children: .combine)
    }

    private func title(_ name: String, count: Int, symbol: String) -> some View {
        HStack(spacing: 7) {
            Image(systemName: symbol).foregroundStyle(.secondary)
            Text(name).font(.system(size: 13, weight: .semibold))
            Spacer()
            if tab != 2 {
                Text("\(count)").font(.system(size: 11)).foregroundStyle(.secondary)
            }
        }
    }

    private func noItems(_ text: String, symbol: String) -> some View {
        HStack(spacing: 9) {
            Image(systemName: symbol).font(.system(size: 16)).foregroundStyle(.secondary)
            Text(text).font(.system(size: 12)).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(13)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.32), in: RoundedRectangle(cornerRadius: 10))
    }

    private var nowContent: some View {
        VStack(alignment: .leading, spacing: 11) {
            title("Grabando / En curso", count: dvr.active.count, symbol: "record.circle.fill")
            if dvr.active.isEmpty {
                noItems("No hay grabaciones activas", symbol: "checkmark.circle")
            } else {
                ForEach(dvr.active) { job in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(job.title).font(.system(size: 13, weight: .semibold)).lineLimit(2)
                            Spacer()
                            Text("REC").font(.system(size: 11, weight: .bold))
                                .foregroundStyle(.red)
                        }
                        Text("\(job.channel) · \(job.statusLabel)")
                            .font(.system(size: 12)).foregroundStyle(.secondary)
                        ProgressView(value: job.progress).tint(.red)
                        HStack {
                            Text("\(job.elapsed) transcurridos · \(job.received)")
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                            Spacer()
                            if job.canCancel {
                                Button("Detener") { dvr.cancel(job) }
                                    .controlSize(.small)
                            }
                        }
                    }
                    .padding(12)
                    .background(Color(nsColor: .controlBackgroundColor).opacity(0.32), in: RoundedRectangle(cornerRadius: 10))
                }
            }
            Divider()
            title("Próximas grabaciones", count: dvr.upcoming.count, symbol: "calendar.badge.clock")
            if dvr.upcoming.isEmpty {
                noItems("No hay grabaciones programadas", symbol: "calendar")
            } else {
                ForEach(dvr.upcoming) { job in
                    HStack(spacing: 8) {
                        Image(systemName: "calendar.badge.clock").foregroundStyle(.orange)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(job.title).font(.system(size: 12, weight: .medium)).lineLimit(2)
                            Text("\(job.channel) · \(job.start.formatted(date: .abbreviated, time: .shortened))")
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 4)
                        if job.canCancel {
                            Button { dvr.cancel(job) } label: { Image(systemName: "xmark.circle") }
                                .help("Cancelar programación")
                                .accessibilityLabel("Cancelar \(job.title)")
                        }
                    }
                    .padding(.vertical, 5)
                }
            }
        }
        .buttonStyle(.bordered)
    }

    private var libraryContent: some View {
        VStack(alignment: .leading, spacing: 10) {
            title("Grabaciones disponibles", count: available.count, symbol: "externaldrive.fill")
            if available.isEmpty {
                noItems("Todavía no hay grabaciones en el disco", symbol: "folder.badge.questionmark")
            } else {
                ForEach(available) { job in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                            .font(.system(size: 15))
                            .padding(.top, 2)
                        VStack(alignment: .leading, spacing: 5) {
                            Text(job.title).font(.system(size: 12, weight: .semibold)).lineLimit(2)
                            Text("\(job.channel) · \(job.received) · \(job.statusLabel)")
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                            HStack(spacing: 8) {
                                Button("Reproducir") { dvr.verEnSYN93(job) }
                                    .help("Abrir esta grabación dentro de SYN")
                                Button { dvr.showFile(job) } label: { Image(systemName: "folder") }
                                    .help("Mostrar archivo en Finder")
                                    .accessibilityLabel("Mostrar \(job.title) en Finder")
                                if adsEnabled {
                                    Button {
                                        dvr.removeCommercials(job)
                                    } label: {
                                        Label(dvr.processingCommercials.contains(job.id) ? "Procesando…" : "Quitar anuncios",
                                              systemImage: "scissors")
                                    }
                                    .disabled(dvr.processingCommercials.contains(job.id))
                                    .help("Genera otra copia sin los cortes que detecte Comskip")
                                }
                            }
                            .controlSize(.small)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(nsColor: .controlBackgroundColor).opacity(0.32), in: RoundedRectangle(cornerRadius: 10))
                }
            }
            Divider()
            Toggle("Mostrar archivos eliminados o no disponibles (\(missing.count))", isOn: $showMissing)
                .font(.system(size: 12))
                .toggleStyle(.checkbox)
            if showMissing {
                if missing.isEmpty {
                    noItems("No hay archivos ausentes", symbol: "checkmark.circle")
                } else {
                    ForEach(missing) { job in
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundStyle(.orange)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(job.title).font(.system(size: 12, weight: .medium)).lineLimit(2)
                                Text("\(job.channel) · \(job.statusLabel) · archivo ausente")
                                    .font(.system(size: 11)).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 4)
                            Button("Olvidar") { dvr.forgetMissing(job) }
                                .help("Quitar del historial; nunca borra vídeos")
                                .controlSize(.small)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
        }
        .buttonStyle(.bordered)
    }

    private var settingsContent: some View {
        VStack(alignment: .leading, spacing: 13) {
            title("Grabaciones", count: 0, symbol: "gearshape")
            HStack {
                Text("Conexiones IPTV simultáneas")
                    .font(.system(size: 12, weight: .medium))
                Spacer()
                Picker("Conexiones", selection: $connections) {
                    ForEach(1...8, id: \.self) { n in Text("\(n)").tag(n) }
                }
                .labelsHidden()
                .frame(width: 75)
                .onChange(of: connections) { _, newValue in
                    if newValue != dvr.capacity { dvr.saveCapacity(newValue) }
                }
            }
            Button { synUA43SheetOpen = true } label: {
                Label("Configurar grabación y User-Agent", systemImage: "slider.horizontal.3")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            Divider()
            HStack(alignment: .center, spacing: 9) {
                Toggle("Habilitar eliminación de anuncios", isOn: $adsEnabled)
                    .font(.system(size: 12, weight: .medium))
                    .toggleStyle(.checkbox)
                Button { showAdHelp.toggle() } label: {
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 13))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Riesgos de quitar anuncios")
                .help("La detección puede confundir partes del programa con anuncios")
                .popover(isPresented: $showAdHelp, arrowEdge: .trailing) {
                    VStack(alignment: .leading, spacing: 9) {
                        Label("Aviso sobre los anuncios", systemImage: "exclamationmark.triangle.fill")
                            .font(.headline).foregroundStyle(.orange)
                        Text("Comskip detecta pausas de forma aproximada: puede eliminar fragmentos del programa o dejar anuncios.")
                        Text("Cuando actives esta opción, podrás pulsar «Quitar anuncios» en cada grabación terminada. Se crea una copia nueva y se conserva siempre el original.")
                        Text("Comskip y FFmpeg vienen incluidos en SYN DVR. Los cortes pueden ser imprecisos al copiar sin recodificar.")
                            .foregroundStyle(.secondary)
                    }
                    .font(.system(size: 12))
                    .padding(16)
                    .frame(width: 305)
                }
            }
            if adsEnabled {
                Text("Disponible en Grabaciones → Quitar anuncios. El original no se modifica.")
                    .font(.system(size: 11)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Divider()
            title("Servicios y avisos", count: 0, symbol: "server.rack")
            HStack(alignment: .center, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Servidor autónomo").font(.system(size: 12, weight: .semibold))
                    Text(synStandalone42.detail).font(.system(size: 11)).foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer(minLength: 4)
                if synStandalone42.enabled {
                    Button(synStandalone42.running ? "Detener" : "Iniciar") {
                        if synStandalone42.running && !dvr.active.isEmpty { synStopConfirmation42 = true }
                        else if synStandalone42.running { synStandalone42.stop() }
                        else { synStandalone42.start() }
                    }
                }
            }
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Notificaciones").font(.system(size: 12, weight: .semibold))
                    Text(synNotifications42.detail).font(.system(size: 11)).foregroundStyle(.secondary)
                }
                Spacer()
                Button(synNotifications42.enabled ? "Desactivar" : "Activar") {
                    synNotifications42.toggle()
                }
            }
            Button { synServerSettingsOpen40 = true } label: {
                Label("Configurar servidor y acceso remoto", systemImage: "network")
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .buttonStyle(.bordered)
        .controlSize(.regular)
    }
}

// SYN_DVR_REMOTE_SETTINGS_40 · only configures the HTTPS gateway, never FFmpeg.
private struct SYNRemoteServerSettings40: View {
    @Environment(\.dismiss) private var dismiss
    @State private var port = "8090"
    @State private var lanEnabled = true
    @State private var folder = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Movies/SYN Grabaciones").path
    @State private var password = ""
    @State private var passwordEnabled = false
    @State private var alreadyHasPassword = false
    @State private var information = ""
    @State private var message = ""
    @State private var busy = false
    @State private var serverActive = false
    @State private var diskText = "—"
    @State private var ramText = "—"
    @State private var pressureText = "No disponible"
    @State private var usedConnections = "—"

    private var support: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Remote")
    }
    private var program: URL { SYNBundledRuntime446.remote ?? support.appendingPathComponent("syn_dvr_remote.py") }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                Image(systemName:"server.rack").foregroundStyle(.teal)
                Text("SYN DVR · Servidor local").font(.title3.bold())
                Spacer()
                Circle().fill(serverActive ? Color.green : Color.orange).frame(width:9,height:9)
                Text(serverActive ? "Conectado" : "No disponible")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Tu grabador sigue siendo independiente. Configura cómo se conectan otros dispositivos, sin alterar la captura actual.")
                .font(.caption).foregroundStyle(.secondary)
            Divider()
            HStack {
                Text("IP local")
                Spacer()
                Text(localAddress).textSelection(.enabled).monospacedDigit()
                Button { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(localAddress,forType:.string) } label: {
                    Image(systemName:"doc.on.doc")
                }.buttonStyle(.plain).help("Copiar IP")
            }
            HStack {
                Text("Puerto HTTPS")
                Spacer()
                TextField("8090",text:$port).frame(width:88).multilineTextAlignment(.trailing)
            }
            Toggle("Permitir conexiones desde la red local",isOn:$lanEnabled)
            HStack {
                Text("Carpeta de grabaciones")
                Spacer()
                Text(folder.isEmpty ? "Sin configurar" : (folder as NSString).lastPathComponent)
                    .lineLimit(1).foregroundStyle(.secondary)
                Button("Elegir…") { chooseFolder() }
            }
            Toggle("Proteger acceso con contraseña",isOn:$passwordEnabled)
            if passwordEnabled {
                SecureField(alreadyHasPassword ? "Nueva contraseña (en blanco: conservar)" : "Contraseña",text:$password)
                    .textFieldStyle(.roundedBorder)
                Text("Sin longitud mínima. La contraseña nunca se guarda en texto plano.")
                    .font(.system(size:10)).foregroundStyle(.tertiary)
            } else if lanEnabled {
                Text("Atención: sin contraseña, cualquier dispositivo de tu red local podrá consultar y gestionar grabaciones.")
                    .font(.caption).foregroundStyle(.orange)
            }
            Divider()
            Group {
                HStack { Label("Disco disponible",systemImage:"externaldrive"); Spacer(); Text(diskText) }
                HStack { Label("RAM instalada",systemImage:"memorychip"); Spacer(); Text(ramText) }
                HStack { Label("Presión de memoria",systemImage:"waveform.path.ecg"); Spacer(); Text(pressureText) }
                HStack { Label("Conexiones IPTV",systemImage:"antenna.radiowaves.left.and.right"); Spacer(); Text(usedConnections) }
            }.font(.system(size:12))
            if !information.isEmpty {
                Text(information).font(.system(size:10,design:.monospaced))
                    .textSelection(.enabled).foregroundStyle(.secondary)
            }
            if !message.isEmpty { Text(message).font(.caption).foregroundStyle(.secondary) }
            HStack {
                Button("Actualizar estado") { load() }
                Spacer()
                Button("Cerrar") { dismiss() }
                Button("Guardar y aplicar") { save() }.buttonStyle(.borderedProminent).disabled(busy)
            }
        }
        .padding(20)
        .frame(width:480)
        .onAppear { load() }
    }

    private var localAddress: String {
        let output = shell("/sbin/ifconfig",[])
        let pattern = #"inet (\d+\.\d+\.\d+\.\d+)"#
        guard let regex = try? NSRegularExpression(pattern:pattern) else { return "127.0.0.1" }
        let ns=output as NSString
        for match in regex.matches(in:output,range:NSRange(location:0,length:ns.length)) {
            let address=ns.substring(with:match.range(at:1))
            if !address.hasPrefix("127.") && !address.hasPrefix("169.254.") { return address }
        }
        return "127.0.0.1"
    }

    private func shell(_ executable:String,_ arguments:[String]) -> String {
        let p=Process();p.executableURL=URL(fileURLWithPath:executable);p.arguments=arguments
        let out=Pipe();p.standardOutput=out;p.standardError=FileHandle.nullDevice
        do { try p.run() } catch { return "" }
        let data=out.fileHandleForReading.readDataToEndOfFile();p.waitUntilExit()
        return String(data:data,encoding:.utf8) ?? ""
    }

    private func load() {
        let fm=FileManager.default
        if SYNBundledRuntime446.available {
            do { try SYNBundledRuntime446.prepare() }
            catch {
                message = "No puedo preparar tus datos: " + error.localizedDescription
                return
            }
        }
        let cfg=support.appendingPathComponent("server.json")
        if let data=try? Data(contentsOf:cfg),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any] {
            port=String(json["port"] as? Int ?? 8090)
            folder=json["recordingsFolder"] as? String ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Movies/SYN Grabaciones").path
            lanEnabled=(json["bind"] as? String ?? "127.0.0.1") != "127.0.0.1"
            passwordEnabled=json["authRequired"] as? Bool ?? fm.fileExists(atPath:support.appendingPathComponent("auth.json").path)
            alreadyHasPassword=fm.fileExists(atPath:support.appendingPathComponent("auth.json").path)
        }
        if fm.isExecutableFile(atPath:program.path) {
            information=shell(SYNBundledRuntime446.python?.path ?? "/usr/bin/python3",[program.path,"info"])
        } else { information="Instala primero SYN DVR Remote 4.1." }
        if let data=try? Data(contentsOf:support.appendingPathComponent("server.heartbeat.json")),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any],
           let stamp=json["timestamp"] as? Double {
            serverActive=abs(Date().timeIntervalSince1970-stamp) < 60
        } else { serverActive=false }
        if !folder.isEmpty,
           let attr=try? fm.attributesOfFileSystem(forPath:folder),
           let free=attr[.systemFreeSize] as? NSNumber {
            diskText=ByteCountFormatter.string(fromByteCount:free.int64Value,countStyle:.file)
        }
        ramText=ByteCountFormatter.string(fromByteCount:Int64(ProcessInfo.processInfo.physicalMemory),countStyle:.memory)
        switch shell("/usr/sbin/sysctl",["-n","kern.memorystatus_vm_pressure_level"]).trimmingCharacters(in:.whitespacesAndNewlines) {
        case "1": pressureText="Normal"
        case "2": pressureText="Moderada"
        case "4": pressureText="Crítica"
        default: pressureText="No disponible"
        }
        let pool=fm.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/SYN DVR Engine 2.0/pool.status.json")
        if let data=try? Data(contentsOf:pool),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any],
           let n=json["occupied"] as? Int, let m=json["maxConnections"] as? Int {
            usedConnections="\(n) / \(m)"
        }
    }

    private func chooseFolder() {
        let panel=NSOpenPanel()
        panel.canChooseDirectories=true;panel.canChooseFiles=false
        panel.allowsMultipleSelection=false;panel.canCreateDirectories=true
        if panel.runModal() == .OK, let url = panel.url { folder = url.path }
    }

    private func save() {
        if SYNBundledRuntime446.available {
            do { try SYNBundledRuntime446.prepare() }
            catch { message = "No puedo guardar en tu carpeta de usuario: " + error.localizedDescription; return }
        }
        guard let n=Int(port), (1024...65535).contains(n), !folder.isEmpty else {
            message="Indica un puerto entre 1024 y 65535 y una carpeta válida.";return
        }
        guard !passwordEnabled || !password.isEmpty || alreadyHasPassword else {
            message="Introduce una contraseña o desactiva la protección.";return
        }
        guard FileManager.default.isExecutableFile(atPath:program.path) else {
            message="Primero instala la API SYN DVR Remote.";return
        }
        busy=true
        let payload:[String:Any]=["bind":lanEnabled ? "0.0.0.0" : "127.0.0.1",
                                  "port":n,"recordingsFolder":folder,"password":passwordEnabled ? password : "",
                                  "authRequired":passwordEnabled]
        DispatchQueue.global(qos:.userInitiated).async {
            let p=Process();p.executableURL=URL(fileURLWithPath:SYNBundledRuntime446.python?.path ?? "/usr/bin/python3")
            p.arguments=[program.path,"configure-stdin"]
            let pipe=Pipe();let result=Pipe()
            p.standardInput=pipe;p.standardOutput=result;p.standardError=result
            var outcome=""
            do {
                let bytes=try JSONSerialization.data(withJSONObject:payload)
                try p.run()
                pipe.fileHandleForWriting.write(bytes)
                try? pipe.fileHandleForWriting.close()
                let data=result.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
                outcome=String(data:data,encoding:.utf8) ?? ""
                if p.terminationStatus==0 {
                    DispatchQueue.main.async {
                        password = ""
                        SYNStandaloneController42.shared.reloadAPI()
                    }
                }
            } catch { outcome=error.localizedDescription }
            DispatchQueue.main.async { busy=false;message=outcome;load() }
        }
    }
}


// SYN_DVR_STANDALONE42 — the menu app owns its own HTTPS and recorder processes.
@MainActor
private final class SYNStandaloneController42: ObservableObject {
    static let shared = SYNStandaloneController42()
    @Published private(set) var running = false
    @Published private(set) var detail = "Servidor detenido"
    private var process: Process?
    private var input: Pipe?
    private var timer: Timer?
    private var startDate: Date?
    private let fm = FileManager.default

    private var support: URL { fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/SYN DVR Remote") }
    private var marker: URL { support.appendingPathComponent("standalone.enabled") }
    private var script: URL { SYNBundledRuntime446.supervisor ?? support.appendingPathComponent("standalone_supervisor.py") }
    private var status: URL { support.appendingPathComponent("standalone.status.json") }
    var enabled: Bool { SYNBundledRuntime446.available || fm.fileExists(atPath:marker.path) }

    private init() {
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in self?.refresh() }
        }
        if enabled { DispatchQueue.main.async { self.start() } }
    }

    func start() {
        guard enabled else { detail = "Activa primero el modo autónomo"; return }
        if process?.isRunning == true { refresh(); return }
        // SYN_DVR_PLUG_PLAY_446: first-run preparation is automatic.
        // No external Python, Homebrew, installer or user terminal is needed.
        if SYNBundledRuntime446.available {
            do { try SYNBundledRuntime446.prepare() }
            catch { detail = "Runtime autónomo incompleto: \(error.localizedDescription)"; return }
        }
        guard fm.fileExists(atPath:script.path) else { detail = "Falta el supervisor autónomo"; return }
        let child = Process()
        let pipe = Pipe()
        child.executableURL = SYNBundledRuntime446.python ?? URL(fileURLWithPath:"/usr/bin/python3")
        child.arguments = [script.path, "run"]
        if SYNBundledRuntime446.available { child.environment = SYNBundledRuntime446.environment() }
        child.standardInput = pipe
        let bootLog = support.appendingPathComponent("autostart-gui.log")
        if !fm.fileExists(atPath: bootLog.path) {
            _ = fm.createFile(atPath: bootLog.path, contents: nil)
        }
        if let writer = try? FileHandle(forWritingTo: bootLog) {
            writer.seekToEndOfFile()
            child.standardOutput = writer
            child.standardError = writer
        } else {
            child.standardOutput = FileHandle.nullDevice
            child.standardError = FileHandle.nullDevice
        }
        do {
            try child.run()
            process = child
            input = pipe
            startDate = Date()
            detail = "Iniciando motor DVR…"
        } catch {
            detail = "No se pudo iniciar: \(error.localizedDescription)"
            running = false
            process = nil
            input = nil
        }
    }

    func refresh() {
        guard let child = process else {
            running = false
            if !enabled { detail = "Activación pendiente" }
            return
        }
        guard child.isRunning else {
            if running { SYNRecordingNotifier42.shared.serverStopped() }
            process = nil
            input = nil
            running = false
            if let data = try? Data(contentsOf:status),
               let obj = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
               let reason = obj["detail"] as? String, !reason.isEmpty {
                detail = "Error: \(reason)"
            } else { detail = "Servidor detenido" }
            return
        }
        guard let data = try? Data(contentsOf:status),
              let obj = try? JSONSerialization.jsonObject(with:data) as? [String:Any],
              let pid = obj["supervisorPID"] as? Int, pid == Int(child.processIdentifier),
              let timestamp = obj["timestamp"] as? Double,
              Date().timeIntervalSince1970 - timestamp < 6,
              let state = obj["state"] as? String else {
            running = false
            if (startDate.map { Date().timeIntervalSince($0) < 22 } ?? false) {
                detail = "Comprobando servidor…"
            } else { detail = "Sin respuesta del supervisor" }
            return
        }
        running = state == "running"
        let message = obj["detail"] as? String ?? ""
        if running {
            detail = message.isEmpty ? "Motor DVR activo" : message
        } else {
            detail = message.isEmpty ? "Estado: \(state)" : message
        }
    }

    func reloadAPI() {
        guard let child = process, child.isRunning, let input else { return }
        input.fileHandleForWriting.write(Data("reload\n".utf8))
        detail = "Actualizando puerto y servidor HTTPS…"
    }

    func stop() {
        guard let input else { running = false; detail = "Servidor detenido"; return }
        SYNRecordingNotifier42.shared.serverStopped()
        // Closing stdin tells the supervisor to stop engine + all its FFmpeg
        // and HTTPS sessions. This also happens after an app crash/Force Quit.
        input.fileHandleForWriting.closeFile()
        self.input = nil
        running = false
        detail = "Deteniendo servidor y grabaciones…"
    }

    var hasActiveRecording: Bool {
        let jobs = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/jobs")
        guard let contents = try? fm.contentsOfDirectory(at:jobs, includingPropertiesForKeys:nil) else { return false }
        for file in contents where file.lastPathComponent.hasSuffix(".status.json") {
            if let bytes = try? Data(contentsOf:file),
               let obj = try? JSONSerialization.jsonObject(with:bytes) as? [String:Any],
               let state = obj["state"] as? String,
               ["recording","reconnecting","retrying","stopping","waiting_for_tuner"].contains(state) { return true }
        }
        return false
    }
}

@MainActor
private final class SYNStandaloneAppDelegate42: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // The menubar popover is lazy: scheduled recordings must start WITHOUT
        // the user opening it. Force initialization on application launch.
        _ = SYNStandaloneController42.shared
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard SYNStandaloneController42.shared.hasActiveRecording else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "¿Cerrar SYN DVR y detener las grabaciones?"
        alert.informativeText = "A diferencia del modo launchd, el motor autónomo se detendrá al cerrar esta aplicación."
        alert.alertStyle = .warning
        alert.addButton(withTitle:"Cancelar")
        alert.addButton(withTitle:"Cerrar y detener")
        return alert.runModal() == .alertSecondButtonReturn ? .terminateNow : .terminateCancel
    }
    func applicationWillTerminate(_ notification: Notification) {
        SYNStandaloneController42.shared.stop()
    }
}


// SYN_DVR_NOTIFICATIONS42 — silent, one notification per meaningful transition.
@MainActor
final class SYNRecordingNotifier42: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = SYNRecordingNotifier42()
    @Published private(set) var enabled = UserDefaults.standard.bool(forKey: "syn.dvr.silentNotifications42")
    @Published private(set) var detail = "Avisos desactivados"
    private var previous: [String:String] = [:]
    private var labels: [String:String] = [:]
    private var baselineReady = false
    private let center = UNUserNotificationCenter.current()

    private override init() {
        super.init()
        center.delegate = self
        if enabled { detail = "Avisos silenciosos activados" }
    }

    func toggle() {
        if enabled {
            enabled = false
            UserDefaults.standard.set(false, forKey:"syn.dvr.silentNotifications42")
            detail = "Avisos desactivados"
            return
        }
        center.requestAuthorization(options:[.alert, .badge]) { [weak self] granted, error in
            Task { @MainActor in
                guard let self else { return }
                self.enabled = granted
                UserDefaults.standard.set(granted, forKey:"syn.dvr.silentNotifications42")
                self.detail = granted ? "Avisos silenciosos activados" :
                    (error == nil ? "Permite las notificaciones en macOS" : "No se pudo activar el permiso")
            }
        }
    }

    private func category(_ state:String) -> String {
        switch state {
        case "recording": return "recording"
        case "retrying", "reconnecting", "waiting_for_tuner": return "interrupted"
        case "finished", "completed": return "finished"
        case "cancelled": return "cancelled"
        case "partial": return "partial"
        case "failed", "expired": return "failed"
        default: return "other"
        }
    }

    func observe(_ jobs:[MenuDVRJob]) {
        let next = Dictionary(uniqueKeysWithValues:jobs.map { ($0.id, $0.state) })
        let names = Dictionary(uniqueKeysWithValues:jobs.map { ($0.id, "\($0.title) · \($0.channel)") })
        defer { labels = names }
        // Never flood with old tasks when the application starts or first gains access.
        guard baselineReady else { previous = next; baselineReady = true; return }
        defer { previous = next }
        // Never announce recovered recording while the app-owned server is stopped.
        guard enabled && SYNStandaloneController42.shared.running else { return }
        for job in jobs {
            let old = previous[job.id].map(category) ?? "other"
            let current = category(job.state)
            if old == current { continue }
            let name = job.title.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty ? job.channel : job.title
            let context = "\(name) · \(job.channel)"
            switch current {
            case "recording":
                if old == "interrupted" { send("Señal recuperada", context, jobID:job.id, state:current) }
                else if old != "finished" && old != "cancelled" && old != "partial" && old != "failed" {
                    send("Grabación iniciada", context, jobID:job.id, state:current)
                }
            case "interrupted":
                if old == "recording" { send("Grabación interrumpida", context + " · Reconectando…", jobID:job.id, state:current) }
            case "finished":
                send("Grabación finalizada", context, jobID:job.id, state:current)
            case "cancelled":
                send("Grabación cancelada", context, jobID:job.id, state:current)
            case "partial":
                send("Grabación parcial", context + " · Revisa el archivo", jobID:job.id, state:current)
            case "failed":
                send("Error en la grabación", context + " · Comprueba el DVR", jobID:job.id, state:current)
            default: break
            }
        }
    }

    // A manual stop or loss of the app-owned server may leave the last on-disk
    // state as "recording". Report the interruption without waiting for the
    // engine to update that status; do not repeat notifications on every tick.
    func serverStopped() {
        guard enabled, baselineReady else { return }
        for (id, state) in previous where category(state) == "recording" {
            send("Grabación interrumpida", (labels[id] ?? "Grabación") + " · Servidor detenido",
                 jobID:id, state:"server-stopped")
            previous[id] = "retrying"
        }
    }

    private func send(_ title:String, _ body:String, jobID:String, state:String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = nil // Explicitly silent. User's macOS notification preferences still apply.
        content.badge = nil
        let request = UNNotificationRequest(identifier:"syn.dvr.42.\(jobID).\(state).\(UUID().uuidString)",
                                            content:content, trigger:nil)
        center.add(request) { error in
            if let error { NSLog("SYN DVR: no se pudo mostrar aviso: %@", error.localizedDescription) }
        }
    }

    nonisolated func userNotificationCenter(_ center:UNUserNotificationCenter,
                                            willPresent notification:UNNotification,
                                            withCompletionHandler completionHandler:@escaping (UNNotificationPresentationOptions)->Void) {
        completionHandler([.banner, .list]) // No .sound
    }
}


// SYN_DVR_RECORDER_UA43_MENU — independent settings for provider-facing FFmpeg.
private struct SYNRecorderUA43Settings: View {
    @Environment(\.dismiss) private var dismiss
    @State private var preset = "vlc"
    @State private var custom = ""
    @State private var feedback = ""
    private let base = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
    private var file: URL { base.appendingPathComponent("recorder-user-agent.json") }

    private var agents: [String: String] {
        ["vlc": "VLC/3.0.21 LibVLC/3.0.21",
         "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
         "chrome": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
         "firefox": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
         "kodi": "Kodi/21.0"]
    }
    private var effective: String { preset == "custom" ? custom : (agents[preset] ?? agents["vlc"]!) }
    private var valid: Bool {
        !effective.isEmpty && effective.utf8.count <= 512 &&
        !effective.unicodeScalars.contains { $0.value < 32 || $0.value == 127 }
    }
    private func load() {
        guard let data = try? Data(contentsOf: file),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        let p = value["preset"] as? String ?? "vlc"
        if agents[p] != nil || p == "custom" { preset = p }
        if let saved = value["custom"] as? String { custom = saved }
    }
    private func save() {
        guard valid else { feedback = "Introduce un User-Agent válido (1–512 bytes y sin saltos de línea)."; return }
        do {
            try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
            let payload: [String: Any] = ["preset": preset, "custom": custom, "userAgent": effective]
            let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
            try data.write(to: file, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: NSNumber(value: 0o600)], ofItemAtPath: file.path)
            feedback = "Guardado. Se aplicará en la próxima conexión IPTV; no se interrumpen las actuales."
        } catch { feedback = "No se pudo guardar: \(error.localizedDescription)" }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                Label("User-Agent del grabador", systemImage: "record.circle")
                    .font(.system(size: 17, weight: .semibold))
                Spacer()
                Button("Cerrar") { dismiss() }
            }
            Text("Identidad que utiliza FFmpeg al conectarse al proveedor. Independiente de la opción de VLC en SYN.")
                .font(.system(size: 12)).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Picker("Identificarse como", selection: $preset) {
                Text("VLC (predeterminado)").tag("vlc")
                Text("Safari · macOS").tag("safari")
                Text("Chrome · macOS").tag("chrome")
                Text("Firefox · macOS").tag("firefox")
                Text("Kodi").tag("kodi")
                Text("Personalizado…").tag("custom")
            }
            if preset == "custom" {
                TextField("Escribe el User-Agent", text: $custom)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityLabel("User-Agent personalizado de SYN DVR")
            }
            Text("Importante: el receptor se comparte con la TV en directo. El proveedor verá este User-Agent también al ver un canal a través del motor DVR. Las conexiones existentes no cambian.")
                .font(.system(size: 11)).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if !feedback.isEmpty {
                Text(feedback).font(.system(size: 11))
                    .foregroundStyle(valid ? Color.secondary : Color.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button("Guardar User-Agent") { save() }
                    .disabled(!valid)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 455)
        .onAppear(perform: load)
    }
}
