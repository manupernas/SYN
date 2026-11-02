import SwiftUI
import AppKit
import CryptoKit
import Security

struct ContentView: View {
    // SYN_M3U_XMLTV_79: perfiles M3U independientes de Xtream.
    @StateObject private var profiles = ProfileStore()
    @StateObject private var synM3UStore79 = SYNM3UStore79()
    @AppStorage("syn.native.activeM3U79") private var synActiveM3UID79 = ""
    @State private var synM3UPlaying79: SYNM3UChannel79? = nil
    @State private var synProfileTypePicker79 = false
    @State private var synSetupOffered7101 = false
    @State private var synEditingXtream7101: XtreamProfile? = nil
    @State private var synM3UEditGuide79: SYNM3UProfile79? = nil
    @State private var synM3UDeleteID79: UUID? = nil
    private var synM3UProfile79: SYNM3UProfile79? {
        synM3UStore79.profiles.first { $0.id.uuidString == synActiveM3UID79 }
    }
    private var synM3UNowNext79: (SYNProgram70, SYNProgram70) {
        let empty = SYNProgram70(title: "", start: nil, end: nil)
        guard let channel = synM3UPlaying79 else { return (empty, empty) }
        let entries = synM3UStore79.channelGuide(channel)
        let now = Date()
        let current = entries.first { $0.start <= now && now < $0.end }
        let next = entries.first { $0.start > now }
        return (current.map { SYNProgram70(title: $0.title, start: $0.start, end: $0.end) } ?? empty,
                next.map { SYNProgram70(title: $0.title, start: $0.start, end: $0.end) } ?? empty)
    }
    private func synM3UTune79(_ channel: SYNM3UChannel79) {
        synM3UPlaying79 = channel
    }
    private func synM3USelect79(_ profile: SYNM3UProfile79) {
        synM3UPlaying79 = nil
        synActiveM3UID79 = profile.id.uuidString
        state.section = .tv
    }
    @StateObject private var state = SYNState()
    // SYN_DVR_SHARED_70: force UI refresh on shared recording stop/start.
    @State private var sharedRecorderRefresh70 = 0
    @State private var synRecordingCount71 = 0
    @State private var synDVRRetryingCount803 = 0 // SYN_DVR_STATUS_803
    @State private var synNotice71 = ""
    @State private var synIssuesSeen71 = Set<String>()
    @State private var synWasRecording71 = false
    // SYN_EPG_MARGINS_90: per-program prompt, scheduling uses the existing unified DVR queue.
    @State private var synEPGPending90: SYNEPGMarginRequest90?
    @State private var synDVR54Message = ""
    @State private var synDVR54Jobs: [(id: String, title: String, start: Date, end: Date, state: String)] = []
    @StateObject private var synDVR53 = SYNDVRRecorder53()
    // SYN_RECORDING_IN_WINDOW_94
    @ObservedObject private var synRecording94 = SYNRecordingWindow93.shared
    // SYN_DVR_UI_98: borrar solo mediante Papelera y ocultar tareas archivadas sin vídeo.
    @State private var synDVRDeleteCandidate98: URL? = nil
    @State private var synDVRDeleteConfirmation98 = false
    @State private var synDVRHiddenJobs98: Set<String> = Set(UserDefaults.standard.stringArray(forKey: "syn.native.dvr.hiddenJobs98") ?? [])
    // SYN_RECORDING_PANEL_95: ventana normal con sidebar; fullscreen sin sidebar.
    @State private var synRecordingFullscreen95 = false
    @AppStorage("syn.native.dvrFolderPath.v1") private var synDVRFolderPath75 = ""
    @State private var synDVR55Day = Date()
    @State private var synDVR55StartHour = 19
    @State private var synDVR55StartMinute = 0
    @State private var synDVR55EndHour = 20
    @State private var synDVR55EndMinute = 0
    // SYN_GUIDE_DVR_73 — navegación real y selección de canales con búsqueda.
    @State private var synDVR55ChannelID = ""
    @State private var synDVRPickerOpen73 = false
    @State private var synDVRSearch73 = ""
    // SYN_FIX74_CATALOG: la lista del DVR y la guía se obtiene de Xtream sin filtro.
    @State private var synCatalog74: [LiveStream] = []
    @State private var synCatalogLoading74 = false
    @State private var synCatalogError74 = ""

    @State private var synGuideCategory73 = ""
    @State private var synGuideSearch73 = ""
    @State private var synGuideFavorites73 = false


    @AppStorage("syn.native.lastProfileID")
    private var lastProfileID = ""
    // SYN_APPLE_APPEARANCE_52: estilos Apple + acento independiente
    @Environment(\.colorScheme) private var systemColorScheme
    @AppStorage("syn.native.appleAppearance") private var appearanceMode = "auto"
    @AppStorage("syn.native.accentMode") private var accentMode = "system"
    @AppStorage("syn.native.accentHex") private var accentHex = "#17A6BB"
    @State private var synSettingsVisible58 = false // SYN_NATIVE_SETTINGS_58
    // SYN_VISUAL_POLISH_78 — barra lateral y cartelera con materiales nativos.
    @State private var synSidebarCollapsed781 = false
    @AppStorage("syn.native.epgGlass78") private var synEPGGlass78 = true
    // SYN_75_REFINEMENTS: selección independiente de reproducción en lista mini.
    @State private var synSelectedChannel75: String? = nil
    @State private var synVisibleLimit = 100
    // SYN_NATIVE_EPG_MULTICANAL_32 — Datos reales del proveedor.
    @State private var synGuideEntries: [String: [EPGEntry]] = [:]
    @State private var synGuideBusy = false
    // SYN_EPG_ATOMIC_77: no publicar filas incompletas.
    @State private var synGuideNextPageBusy77 = false
    @State private var synGuideVisibleCount = 20 // SYN_ALPHA46_PAGINATION
    @State private var synGuideScope = ""
    // SYN_NATIVE_EPG_GTK_33
    // El vídeo tiene prioridad; la guía grande es opcional y recuerda la elección.
    @AppStorage("syn.native.guideExpanded7103") private var synGuideExpanded7103 = false
    @State private var synGuideShiftMinutes: Int = 0
    @State private var synGuideFocusRevision: Int = 0 // SYN_FIX41_CENTER
    // SYN_GTK_PILLS_42: personalización por perfil + ID, conservada en el Mac.
    @State private var synLogoOverrides: [String: String] = UserDefaults.standard.dictionary(forKey: "syn.native.logoOverrides") as? [String: String] ?? [:]
    // SYN_PROVIDER_LOGO_REFRESH_96: interfaz y caché específica.
    @State private var synLogoReloadRevision96 = 0
    @State private var synLogoRefreshMessage96 = "Descarga de nuevo los logos originales; conserva los personalizados, perfiles y favoritos."
    @State private var synLogoEditingKey = ""
    @State private var synLogoDraft = ""
    @State private var synLogoURLVisible = false


    @State private var query = ""
    // SYN_76_POSTER_CATALOG: la cartelera cubre visualmente el reproductor,
    // pero no lo desmonta ni reinicia al cambiar de sección.
    @State private var synLibraryPlayer76 = false
    @State private var synLibraryEpisodesOpen76 = false


    // Lista calculada fuera de ForEach.
    private var synDisplayedChannels: [LiveStream] {
        let category = state.chosenCategory
        let search = state.query
        let onlyFavorites = state.section == .favorites
        let profilePrefix = (state.selectedProfile?.id.uuidString ?? "no-profile") + ":"
        let favoriteKeys = state.favorites

        return state.channels.filter { channel in
            if !category.isEmpty && channel.categoryID?.value != category {
                return false
            } 
            if !search.isEmpty &&
               !channel.name.localizedCaseInsensitiveContains(search) {
                return false
            }

            if onlyFavorites &&
               !favoriteKeys.contains(profilePrefix + channel.id) {
                return false
            }

            return true
        }
    }

    private var colors: SYNApplePalette52 {
        SYNApplePalette52(
            dark: appearanceMode == "dark" || (appearanceMode == "auto" && systemColorScheme == .dark),
            accent: accentMode == "system" ? Color(nsColor: .controlAccentColor) : SYNApplePalette52.parseHex(accentHex)
        )
    }
    private var chosenColor: Color {
        get { SYNApplePalette52.parseHex(accentHex) }
        nonmutating set { accentHex = SYNApplePalette52.hex(newValue) ?? accentHex }
    }


    private var synBrandHeader: some View {
        HStack(spacing: 10) {
            Image(nsImage: NSApp.applicationIconImage)
                .resizable()
                .interpolation(.high)
                .frame(width: 30, height: 30)
                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                .shadow(color: .black.opacity(0.12), radius: 2, y: 1)

            VStack(alignment: .leading, spacing: 3) {
                Group {
                    if let logo = NSImage(
                        named: NSImage.Name(colors.dark ? "logo_light" : "logo_dark")
                    ) {
                        Image(nsImage: logo)
                            .resizable()
                            .scaledToFit()
                            .frame(height: 12)
                    } else {
                        Text("SYN")
                            .font(.system(size: 16, weight: .bold, design: .rounded))
                    }
                }

                Text(state.selectedProfile?.name ?? synM3UProfile79?.name ?? "SYN")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(colors.muted)
                    .lineLimit(1)
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.top, 10)
        .padding(.bottom, 6)
    }

    private var synEPGHeader: some View {
        HStack(spacing: 10) {
            channelAvatar(state.playingTitle, image: nil)
                .frame(width: 28, height: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(state.playingTitle.isEmpty ? "Selecciona un canal" : state.playingTitle)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)

                Text("Guía de televisión")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(colors.muted)
                    .lineLimit(1)
            }

            Spacer()

            if state.playingURL != nil {
                Text("DIRECTO")
                    .font(.system(size: 9, weight: .bold))
                    .tracking(0.8)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(
                        Capsule().fill(colors.accent.opacity(0.18))
                    )
            }
        }
    }


    var body: some View {
        // El catálogo puede cargarse sin interrumpir el vídeo ni el DVR.
        // SYN_71_STABLE_DVR: single navigation tree; VLCPlayerView never unmounts on DVR tab.
        // DVR hides the channel list, but keeps the same renderer mounted in detailColumn.
        VStack(spacing: 0) {
            // SYN_72_REC_DISCRETO: eliminado el banner que cruzaba la cabecera
            // y restaba espacio al reproductor. REC permanece visible en la sidebar.
            // SYN_SIDEBAR_781 — columna con tamaño fijo; nunca ocupa media ventana.
            HStack(spacing: 0) {
                if !synSidebarCollapsed781 && !(synRecording94.file != nil && synRecordingFullscreen95) {
                    sidebar
                        .transition(.move(edge: .leading).combined(with: .opacity))
                        .frame(width: 244)
                        .frame(maxHeight: .infinity)
                    Divider()
                }
                VStack(spacing: 0) {
                    if !(synRecording94.file != nil && synRecordingFullscreen95) {
                    HStack(spacing: 10) {
                        Button {
                            withAnimation(.easeInOut(duration: 0.22)) {
                                synSidebarCollapsed781.toggle()
                            }
                        } label: {
                            Image(systemName: "sidebar.left")
                                .font(.system(size: 14, weight: .semibold))
                                .frame(width: 27, height: state.section == .tv || state.section == .favorites ? 22 : 28)
                        }
                        .buttonStyle(.plain)
                        .help(synSidebarCollapsed781 ? "Mostrar barra lateral" : "Ocultar barra lateral")
                        .modifier(SYNGlassCard78(corner: 10))
                        // En TV/Favoritos el gran logo lateral ya identifica SYN;
                        // eliminar el rótulo duplicado permite acercar el vídeo arriba.
                        if state.section != .tv && state.section != .favorites {
                            Text("SYN")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 0)
                    }
                    .frame(height: state.section == .tv || state.section == .favorites ? 24 : 38)
                    .padding(.horizontal, 10)
                    Divider().opacity(0.24)
                    }
                    HStack(spacing: 0) {
                    if synRecording94.file == nil && state.section != .dvr && state.section != .movies && state.section != .series && state.section != .epg {
                        if let playlist = synM3UProfile79 {
                            SYNM3UChannelList79(store: synM3UStore79, profile: playlist, onTune: synM3UTune79)
                                // AsyncImage M3U vuelve a consultar sus URLs conocidas.
                                .id(synLogoReloadRevision96)
                                .frame(width: 290)
                        } else {
                            channelColumn.frame(width: 290)
                        }
                        Divider()
                    }
                    // La vista VLC sigue montada; al abrir Guía no se destruye el player.
                    ZStack {
                        detailColumn
                            // Mantener VLC del directo montado y conectado, pero no interactivo.
                            .opacity(state.section == .epg || synRecording94.file != nil ? 0 : 1)
                            .allowsHitTesting(state.section != .epg && synRecording94.file == nil)
                        if state.section == .epg && synRecording94.file == nil {
                            if let playlist = synM3UProfile79 {
                                SYNM3UGuide79(store: synM3UStore79, profile: playlist, onTune: synM3UTune79,
                                    onScheduleEPG90: synAskM3UEPG90)
                                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                            } else {
                                synFullGuide73.frame(maxWidth: .infinity, maxHeight: .infinity)
                            }
                        }
                        // SYN_RECORDING_PANEL_95: el reproductor queda a la derecha
                        // de la sidebar, sin lista de canales ni EPG.
                        if synRecording94.file != nil {
                            synRecordingPanel95
                                .zIndex(10)
                        }
                    }
                    .frame(minWidth: 480, minHeight: 480)
                    }
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .synRecordingPlayback94Changed)) { event in
            if event.userInfo?["active"] as? Bool == true {
                state.section = .dvr
                synSidebarCollapsed781 = false
                synRecordingFullscreen95 = NSApp.mainWindow?.styleMask.contains(.fullScreen) ?? false
            }
        }
        // SYN_RECORDING_ZOOM_99: esperar al final de la animación nativa.
        // No desmontar el vídeo ni reconfigurar el contenido durante el cambio de Space.
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didEnterFullScreenNotification)) { event in
            if synRecording94.file != nil, event.object is NSWindow {
                withAnimation(.easeInOut(duration: 0.36)) {
                    synRecordingFullscreen95 = true
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didExitFullScreenNotification)) { event in
            if event.object is NSWindow {
                withAnimation(.easeInOut(duration: 0.36)) {
                    synRecordingFullscreen95 = false
                }
            }
        }
        .onChange(of: state.query) { _, _ in
            synVisibleLimit = 100
        }
        .onChange(of: state.selectedProfile?.id) { _, _ in
            synSelectedChannel75 = nil
            synCatalog74 = []
            synCatalogError74 = ""
            synDVR55ChannelID = ""
            synGuideEntries.removeAll()
            synGuideScope = ""
        }
        // Works in ALL tabs. Reports starts/stops/failures without opening DVR.
        .onReceive(Timer.publish(every: 2.0, on: .main, in: .common).autoconnect()) { _ in
            synDVR54Jobs = SYNBackgroundDVR54.list()
            let total = synDVR54Jobs.filter { ["recording", "reconnecting", "stopping"].contains($0.state) }.count
            synWasRecording71 = total > 0
            synRecordingCount71 = total
            synRecordingCount71 = total
            // La barra no repite fallos históricos: los estados definitivos quedan en DVR.
            sharedRecorderRefresh70 += 1
        }
                .tint(colors.accent)
        .background(SYNScrollerOverlay795().frame(width: 0, height: 0)) // SYN_SCROLL_OVERLAY_795
        .preferredColorScheme(appearanceMode == "auto" ? nil : (appearanceMode == "dark" ? .dark : .light))
        .frame(minWidth: 1080, minHeight: 660)
        .alert("Cambiar logo de canal", isPresented: $synLogoURLVisible) {
            TextField("https://servidor/logo.png", text: $synLogoDraft)
            Button("Guardar") { synSaveLogoURL() }
            Button("Cancelar", role: .cancel) { }
        } message: {
            Text("URL HTTPS o HTTP de una imagen. Se guarda solo para este canal y perfil.")
        }
        .sheet(item: $synEPGPending90) { request in
            SYNEPGMarginChooser90(title: request.title, epgStart: request.start, epgEnd: request.end) { start, end in
                try SYNBackgroundDVR54.add(url: request.url, channel: request.channel,
                    title: request.title, start: start, end: end, epg: true, eventDate: request.start)
                synDVR54Jobs = SYNBackgroundDVR54.list()
                synDVR54Message = "Grabación programada: " + request.title
            } onClose: {
                synEPGPending90 = nil
            }
        }
        .sheet(isPresented: $synSettingsVisible58) {
            synSettingsSheet58
        }
        .sheet(isPresented: $synProfileTypePicker79) {
            SYNProfileSetup7101(existing: nil, onXtream: synSaveXtream7101, onM3U: synSaveM3U7101)
        }
        .sheet(item: $synEditingXtream7101) { original in
            SYNProfileSetup7101(existing: original, onXtream: synSaveXtream7101, onM3U: synSaveM3U7101)
        }
        .sheet(item: $synM3UEditGuide79) { playlist in
            SYNM3UEditGuide79(store: synM3UStore79, profile: playlist) { updated in
                Task { await synM3UStore79.load(updated) }
            }
        }
        .alert("¿Eliminar perfil M3U?", isPresented: Binding(
            get: { synM3UDeleteID79 != nil }, set: { if !$0 { synM3UDeleteID79 = nil } })) {
            Button("Eliminar perfil", role: .destructive) {
                if let id = synM3UDeleteID79 {
                    synM3UStore79.remove(id)
                    if synActiveM3UID79 == id.uuidString { synActiveM3UID79 = ""; synM3UPlaying79 = nil }
                }
                synM3UDeleteID79 = nil
            }
            Button("Cancelar", role: .cancel) { synM3UDeleteID79 = nil }
        } message: { Text("Se elimina la configuración del perfil; no se borran grabaciones.") }
        .task(id: synActiveM3UID79) {
            if let playlist = synM3UProfile79 { await synM3UStore79.load(playlist) }
        }
        .onAppear {
            if synM3UProfile79 == nil && state.selectedProfile == nil {
                let remembered = profiles.profiles.first { $0.id.uuidString == lastProfileID }
                if let profile = remembered ?? profiles.profiles.first {
                    lastProfileID = profile.id.uuidString
                    state.select(profile)
                }
            }
            // Primera apertura real: sin fuentes se muestra la bienvenida, sin alertas Xtream.
            if !synSetupOffered7101 {
                synSetupOffered7101 = true
                if profiles.profiles.isEmpty && synM3UStore79.profiles.isEmpty {
                    DispatchQueue.main.async { synProfileTypePicker79 = true }
                }
            }
        }
        .alert("Xtream", isPresented: Binding(get: { state.error != nil }, set: { if !$0 { state.error = nil } })) {
            Button("Entendido", role: .cancel) { state.error = nil }
        } message: { Text(state.error ?? "Error desconocido") }
    }

    // SYN_NATIVE_SETTINGS_7102 — panel visual, sin formularios extensos.
    @State private var synSettingsTab58 = 0
    @AppStorage("syn.native.vlc.networkCaching799") private var synVLCNetworkCache799 = 1000
    @AppStorage("syn.native.vlc.hardware799") private var synVLCHardware799 = "auto"
    // SYN_CURSOR_OPTION_11241: persistente, activado por defecto.
    @AppStorage("syn.native.fullscreenHideCursor11241") private var synFullscreenHideCursor11241 = true
    // SYN_PLAYBACK_USER_AGENT_911: guarda la elección sin tocar perfiles ni favoritos.
    @AppStorage("syn.native.vlc.userAgentPreset911") private var synUserAgentPreset911 = "vlc"
    @AppStorage("syn.native.vlc.userAgentCustom911") private var synUserAgentCustom911 = ""
    @State private var synProfileToDelete581: XtreamProfile? = nil
    @State private var synRenameProfile799: XtreamProfile? = nil
    @State private var synRenameText799 = ""

    private var synSettingsSheet58: some View {
        HStack(spacing: 0) {
            // Editorial: la misma familia visual que la bienvenida a SYN.
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 11) {
                    Image(systemName: "play.rectangle.on.rectangle.fill")
                        .font(.system(size: 21, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 42, height: 42)
                        .background(.white.opacity(0.16), in: RoundedRectangle(cornerRadius: 14))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("SYN").font(.system(size: 23, weight: .heavy, design: .rounded))
                        Text("PERSONALIZA TU TELEVISIÓN")
                            .font(.system(size: 9, weight: .semibold))
                            .tracking(1.1)
                            .opacity(0.7)
                    }
                    Spacer()
                }
                .padding(.bottom, 34)
                Text("A tu\nmanera.")
                    .font(.system(size: 35, weight: .bold, design: .rounded))
                    .tracking(-1.1)
                    .lineSpacing(-3)
                    .padding(.bottom, 9)
                Text("Todo lo que necesitas, sin complicarte la vida.")
                    .font(.system(size: 13))
                    .foregroundStyle(.white.opacity(0.76))
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 32)

                VStack(spacing: 10) {
                    synSettingsNav7102("Fuentes", detail: "Perfiles y listas", icon: "square.stack.3d.up.fill", index: 0)
                    synSettingsNav7102("Guía y DVR", detail: "Programas y archivos", icon: "calendar.badge.clock", index: 1)
                    synSettingsNav7102("Reproductor", detail: "Ajusta el directo", icon: "play.square.stack.fill", index: 2)
                    synSettingsNav7102("Apariencia", detail: "Hazlo tuyo", icon: "paintpalette.fill", index: 3)
                }
                Spacer(minLength: 18)
                HStack(spacing: 9) {
                    Image(systemName: "checkmark.shield.fill")
                        .foregroundStyle(Color(red: 0.61, green: 0.96, blue: 0.86))
                    Text("Cambios guardados al instante")
                        .font(.system(size: 11))
                        .foregroundStyle(.white.opacity(0.77))
                }
            }
            .foregroundStyle(.white)
            .padding(27)
            .frame(width: 273)
            .frame(maxHeight: .infinity, alignment: .topLeading)
            .background {
                LinearGradient(
                    colors: [Color(red: 0.08, green: 0.23, blue: 0.31),
                             Color(red: 0.10, green: 0.41, blue: 0.47),
                             Color(red: 0.13, green: 0.26, blue: 0.38)],
                    startPoint: .topLeading, endPoint: .bottomTrailing
                )
            }

            VStack(spacing: 0) {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Ajustes")
                            .font(.system(size: 24, weight: .bold, design: .rounded))
                        Text("Pequeños cambios. Gran experiencia.")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button { synSettingsVisible58 = false } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .semibold))
                            .frame(width: 32, height: 32)
                            .background(.quaternary, in: Circle())
                    }
                    .buttonStyle(.plain)
                    .help("Cerrar Ajustes")
                    .keyboardShortcut(.cancelAction)
                }
                .padding(.horizontal, 30)
                .padding(.top, 28)
                .padding(.bottom, 16)

                ScrollView {
                    Group {
                        switch synSettingsTab58 {
                        case 0: synSettingsProfile58
                        case 1: synSettingsPlayback58
                        case 2: synSettingsAdvancedVLC7101
                        default: synSettingsAppearance58
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 30)
                    .padding(.bottom, 25)
                }
                .scrollIndicators(.hidden)
                HStack {
                    Text("SYN Native")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Listo") { synSettingsVisible58 = false }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .tint(.orange)
                        .keyboardShortcut(.defaultAction)
                }
                .padding(.horizontal, 30)
                .padding(.vertical, 14)
                .background(.ultraThinMaterial)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(colors.dark ? Color(red: 0.10, green: 0.12, blue: 0.15) : Color(red: 0.96, green: 0.97, blue: 0.98))
        }
        .frame(width: 960, height: 675)
        .clipShape(RoundedRectangle(cornerRadius: 19, style: .continuous))
        .alert("Renombrar perfil", isPresented: Binding(
            get: { synRenameProfile799 != nil },
            set: { if !$0 { synRenameProfile799 = nil } }
        )) {
            TextField("Nombre del perfil", text: $synRenameText799)
            Button("Cancelar", role: .cancel) { synRenameProfile799 = nil }
            Button("Guardar") {
                if let target = synRenameProfile799,
                   let renamed = profiles.rename(target.id, to: synRenameText799),
                   state.selectedProfile?.id == renamed.id {
                    state.selectedProfile = renamed
                }
                synRenameProfile799 = nil
            }
        } message: {
            Text("El nombre cambia, pero la conexión, los favoritos y la contraseña se conservan.")
        }
        .alert("Eliminar perfil", isPresented: Binding(
            get: { synProfileToDelete581 != nil },
            set: { if !$0 { synProfileToDelete581 = nil } }
        )) {
            Button("Cancelar", role: .cancel) { synProfileToDelete581 = nil }
            Button("Eliminar perfil", role: .destructive) {
                guard let victim = synProfileToDelete581 else { return }
                synProfileToDelete581 = nil
                guard profiles.profiles.count > 1, profiles.profiles.contains(where: { $0.id == victim.id }) else { return }
                if state.selectedProfile?.id == victim.id {
                    guard let replacement = profiles.profiles.first(where: { $0.id != victim.id }) else { return }
                    lastProfileID = replacement.id.uuidString
                    state.select(replacement)
                }
                profiles.delete(victim.id)
            }
        } message: {
            Text("Se eliminará \(synProfileToDelete581?.name ?? "") y su contraseña del Llavero. No se borrarán grabaciones.")
        }
    }

    private func synSettingsNav7102(_ name: String, detail: String, icon: String, index: Int) -> some View {
        let active = synSettingsTab58 == index
        return Button { synSettingsTab58 = index } label: {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.system(size: 19, weight: .medium))
                    .frame(width: 30)
                VStack(alignment: .leading, spacing: 3) {
                    Text(name).font(.system(size: 14, weight: .semibold))
                    Text(detail).font(.system(size: 10)).opacity(0.7)
                }
                Spacer(minLength: 0)
                if active { Image(systemName: "chevron.right").font(.system(size: 11, weight: .bold)) }
            }
            .padding(.horizontal, 13)
            .padding(.vertical, 14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(active ? Color.white.opacity(0.22) : Color.white.opacity(0.065),
                        in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(.white.opacity(active ? 0.33 : 0.08), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(active ? .isSelected : [])
    }

    private func synSettingsHeading7102(_ title: String, subtitle: String, icon: String) -> some View {
        HStack(alignment: .center, spacing: 13) {
            Image(systemName: icon)
                .font(.system(size: 22, weight: .medium))
                .foregroundStyle(.orange)
                .frame(width: 46, height: 46)
                .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 15))
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.system(size: 23, weight: .bold, design: .rounded))
                Text(subtitle).font(.system(size: 12)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }.padding(.bottom, 6)
    }

    private func synSettingsBlock78<Content: View>(
        _ title: String, caption: String = "", @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(title).font(.system(size: 15, weight: .semibold, design: .rounded))
            if !caption.isEmpty {
                Text(caption).font(.system(size: 11)).foregroundStyle(.secondary)
            }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(Color.primary.opacity(0.055), lineWidth: 1))
    }

    private func synSettingsChoice7102(
        _ title: String, subtitle: String, icon: String, selected: Bool,
        tint: Color = .orange, action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: icon).font(.system(size: 23, weight: .medium))
                        .foregroundStyle(selected ? tint : .secondary)
                    Spacer()
                    if selected {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(tint)
                            .font(.system(size: 17))
                    }
                }
                Spacer(minLength: 0)
                Text(title).font(.system(size: 14, weight: .semibold))
                Text(subtitle).font(.system(size: 10)).foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            .padding(15)
            .frame(maxWidth: .infinity, minHeight: 113, maxHeight: 113, alignment: .leading)
            .background(selected ? tint.opacity(0.11) : Color.primary.opacity(0.035),
                        in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(selected ? tint.opacity(0.7) : Color.primary.opacity(0.07), lineWidth: selected ? 1.5 : 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func synSettingsAction7102(
        _ title: String, subtitle: String, icon: String,
        tint: Color = .orange, enabled: Bool = true,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 13) {
                Image(systemName: icon)
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(tint)
                    .frame(width: 47, height: 47)
                    .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 14))
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.system(size: 14, weight: .semibold))
                    Text(subtitle).font(.system(size: 11)).foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer(minLength: 8)
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(.secondary)
            }
            .padding(13)
            .background(Color.primary.opacity(0.04), in: RoundedRectangle(cornerRadius: 15))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.5)
    }

    private var synSettingsProfile58: some View {
        VStack(alignment: .leading, spacing: 18) {
            synSettingsHeading7102("Tus fuentes", subtitle: "Cambia de perfil o edita una conexión en un toque.", icon: "square.stack.3d.up.fill")
            synSettingsAction7102("Añadir fuente", subtitle: "Xtream o lista M3U · configuración guiada", icon: "plus.circle.fill", tint: .orange) {
                synSettingsVisible58 = false
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { synProfileTypePicker79 = true }
            }
            synSettingsBlock78("Xtream Codes", caption: "Tus claves permanecen protegidas en el Llavero del Mac.") {
                if profiles.profiles.isEmpty {
                    Label("Aún no tienes perfiles Xtream.", systemImage: "sparkles")
                        .foregroundStyle(.secondary)
                }
                ForEach(profiles.profiles) { profile in
                    VStack(alignment: .leading, spacing: 11) {
                        HStack(spacing: 10) {
                            SYNProfileAvatar78(name: profile.name, size: 40)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(profile.name).font(.system(size: 14, weight: .semibold))
                                Text("Xtream").font(.system(size: 11)).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if profile.id == state.selectedProfile?.id && synM3UProfile79 == nil {
                                Label("En uso", systemImage: "checkmark.circle.fill")
                                    .font(.system(size: 11, weight: .medium)).foregroundStyle(.green)
                            } else {
                                Button("Usar") {
                                    synActiveM3UID79 = ""
                                    lastProfileID = profile.id.uuidString
                                    state.select(profile)
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                        HStack(spacing: 9) {
                            Button {
                                synSettingsVisible58 = false
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { synEditingXtream7101 = profile }
                            } label: { Label("Editar conexión", systemImage: "slider.horizontal.3") }
                                .buttonStyle(.borderedProminent).tint(.orange)
                            Button {
                                synRenameText799 = profile.name
                                synRenameProfile799 = profile
                            } label: { Label("Nombre", systemImage: "pencil") }
                                .buttonStyle(.bordered)
                            Spacer()
                            Button(role: .destructive) { synProfileToDelete581 = profile } label: {
                                Image(systemName: "trash").foregroundStyle(.red)
                            }
                            .buttonStyle(.borderless)
                            .disabled(profiles.profiles.count <= 1)
                            .help("Eliminar este perfil")
                        }
                        .controlSize(.small)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 15))
                }
            }
            synSettingsBlock78("Listas M3U", caption: "También puedes asociar programación XMLTV.") {
                if synM3UStore79.profiles.isEmpty {
                    Text("Todavía no tienes listas M3U.").foregroundStyle(.secondary)
                }
                ForEach(synM3UStore79.profiles) { playlist in
                    HStack(spacing: 10) {
                        Image(systemName: "list.bullet.rectangle.portrait.fill")
                            .foregroundStyle(.teal)
                            .frame(width: 34, height: 36)
                            .background(Color.teal.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(playlist.name).font(.system(size: 14, weight: .semibold))
                            Text(playlist.guide.isEmpty ? "Sin guía vinculada" : "Guía XMLTV activa")
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if synActiveM3UID79 != playlist.id.uuidString {
                            Button("Usar") { synM3USelect79(playlist) }.buttonStyle(.bordered)
                        } else {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                        }
                        Button { synM3UEditGuide79 = playlist } label: {
                            Image(systemName: "calendar.badge.plus")
                        }.buttonStyle(.borderless).help("Editar guía XMLTV")
                        Button(role: .destructive) { synM3UDeleteID79 = playlist.id } label: {
                            Image(systemName: "trash").foregroundStyle(.red)
                        }.buttonStyle(.borderless).help("Eliminar lista")
                    }
                    .padding(10)
                    .background(Color.primary.opacity(0.035), in: RoundedRectangle(cornerRadius: 14))
                }
            }
        }
    }

    private var synSettingsPlayback58: some View {
        VStack(alignment: .leading, spacing: 17) {
            synSettingsHeading7102("Guía y grabaciones", subtitle: "Tu programación y tus vídeos, siempre a mano.", icon: "calendar.badge.clock")
            synSettingsBlock78("Televisión en directo") {
                synSettingsAction7102("Actualizar programación", subtitle: "Recarga la guía de la fuente activa", icon: "arrow.clockwise", tint: .teal,
                                      enabled: (state.selectedProfile != nil || synM3UProfile79 != nil) && !synGuideBusy && !synM3UStore79.loading) {
                    if let playlist = synM3UProfile79 {
                        Task { await synM3UStore79.load(playlist) }
                    } else {
                        synGuideScope = ""
                        synGuideEntries.removeAll()
                        Task { await synLoadMultiGuide() }
                    }
                }
            }
            synSettingsBlock78("SYN DVR · Servidor") {
                SYNRemotePairing40()
            }
            synSettingsBlock78("Biblioteca local") {
                synSettingsAction7102("Carpeta de grabaciones", subtitle: synDVR53.folder.lastPathComponent, icon: "record.circle", tint: .red) {
                    synChooseDVRFolder75()
                }
                synSettingsAction7102("Abrir capturas", subtitle: "Tus imágenes guardadas por SYN", icon: "camera.on.rectangle", tint: .teal) {
                    let folder = FileManager.default.homeDirectoryForCurrentUser
                        .appendingPathComponent("Pictures/SYN Capturas", isDirectory: true)
                    try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                    NSWorkspace.shared.open(folder)
                }
            }
        }
    }

    private func synVLCButton7102(_ title: String, milliseconds: Int) -> some View {
        let selected = synVLCNetworkCache799 == milliseconds
        return Button { synVLCNetworkCache799 = milliseconds } label: {
            VStack(spacing: 7) {
                Text(title).font(.system(size: 15, weight: .semibold, design: .rounded))
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 12)).foregroundStyle(selected ? .orange : .secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(selected ? Color.orange.opacity(0.12) : Color.primary.opacity(0.035),
                        in: RoundedRectangle(cornerRadius: 13))
            .overlay(RoundedRectangle(cornerRadius: 13).strokeBorder(selected ? Color.orange : Color.clear, lineWidth: 1.4))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Búfer de \(title)")
    }

    private var synSettingsAdvancedVLC7101: some View {
        VStack(alignment: .leading, spacing: 18) {
            synSettingsHeading7102("Reproductor", subtitle: "Ajusta la reproducción a tu conexión y a tu Mac.", icon: "play.square.stack.fill")
            synSettingsBlock78("Búfer de red", caption: "Menos espera o más estabilidad. Se aplica al cambiar de canal.") {
                HStack(spacing: 8) {
                    synVLCButton7102("0,5 s", milliseconds: 500)
                    synVLCButton7102("1 s", milliseconds: 1000)
                    synVLCButton7102("2 s", milliseconds: 2000)
                    synVLCButton7102("3 s", milliseconds: 3000)
                    synVLCButton7102("5 s", milliseconds: 5000)
                }
                HStack(spacing: 6) {
                    Image(systemName: "bolt.fill").foregroundStyle(.orange)
                    Text("Menos latencia")
                    Spacer()
                    Text("Más estabilidad")
                    Image(systemName: "shield.fill").foregroundStyle(.teal)
                }
                .font(.system(size: 10)).foregroundStyle(.secondary)
            }
            // SYN_PLAYBACK_USER_AGENT_911 — cabeceras de las fuentes abiertas por SYN.
            synSettingsBlock78("User-Agent", caption: "Identificación HTTP de la reproducción. No cambia tu perfil ni las credenciales.") {
                VStack(alignment: .leading, spacing: 10) {
                    Picker("Identificarse como", selection: $synUserAgentPreset911) {
                        Text("VLC (actual · predeterminado)").tag("vlc")
                        Text("Safari · macOS").tag("safari")
                        Text("Chrome · macOS").tag("chrome")
                        Text("Firefox · macOS").tag("firefox")
                        Text("Kodi").tag("kodi")
                        Text("Personalizado…").tag("custom")
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: .infinity, alignment: .leading)

                    if synUserAgentPreset911 == "custom" {
                        TextField("Introduce tu User-Agent HTTP", text: $synUserAgentCustom911)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                        Text(synUserAgentCustom911.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                             ? "Sin valor personalizado se utilizará el User-Agent de VLC."
                             : "Se enviará el texto indicado al abrir una nueva reproducción.")
                            .font(.system(size: 11)).foregroundStyle(.secondary)
                    }
                    Text("Se aplica a VLC al abrir una nueva fuente. En TV, el proveedor ve el User-Agent del motor SYN DVR, que se configura por separado.")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            synSettingsBlock78("Decodificación de vídeo", caption: "Automática aprovecha la aceleración del equipo cuando está disponible.") {
                HStack(spacing: 10) {
                    synSettingsChoice7102("Automática", subtitle: "Recomendada", icon: "cpu", selected: synVLCHardware799 == "auto", tint: .teal) {
                        synVLCHardware799 = "auto"
                    }
                    synSettingsChoice7102("Software", subtitle: "Procesamiento por CPU", icon: "desktopcomputer", selected: synVLCHardware799 == "none") {
                        synVLCHardware799 = "none"
                    }
                }
            }
            synSettingsBlock78("Pantalla completa") {
                Toggle(isOn: $synFullscreenHideCursor11241) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Ocultar cursor en pantalla completa")
                            .font(.system(size: 13, weight: .medium))
                        Text("Se oculta tras 15 segundos sin actividad; vuelve al mover el ratón.")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.checkbox)
            }
            HStack {
                Label("VLC se ajusta al abrir el siguiente vídeo.", systemImage: "info.circle")
                    .font(.system(size: 11)).foregroundStyle(.secondary)
                Spacer()
                Button("Restablecer") {
                    synVLCNetworkCache799 = 1000
                    synVLCHardware799 = "auto"
                    synFullscreenHideCursor11241 = true
                    synUserAgentPreset911 = "vlc"
                    synUserAgentCustom911 = ""
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private var synSettingsAppearance58: some View {
        VStack(alignment: .leading, spacing: 18) {
            synSettingsHeading7102("Apariencia", subtitle: "Tu SYN, con el aspecto que tú elijas.", icon: "paintpalette.fill")
            synSettingsBlock78("Elige tu ambiente") {
                HStack(spacing: 10) {
                    synSettingsChoice7102("Automático", subtitle: "Sigue tu Mac", icon: "circle.lefthalf.filled", selected: appearanceMode == "auto", tint: .teal) {
                        appearanceMode = "auto"
                    }
                    synSettingsChoice7102("Claro", subtitle: "Luminoso", icon: "sun.max.fill", selected: appearanceMode == "light") {
                        appearanceMode = "light"
                    }
                    synSettingsChoice7102("Oscuro", subtitle: "Cine en casa", icon: "moon.stars.fill", selected: appearanceMode == "dark", tint: .indigo) {
                        appearanceMode = "dark"
                    }
                }
            }
            synSettingsBlock78("Color de acento") {
                HStack(spacing: 10) {
                    synSettingsChoice7102("Del sistema", subtitle: "Como tu Mac", icon: "macwindow", selected: accentMode == "system", tint: .teal) {
                        accentMode = "system"
                    }
                    synSettingsChoice7102("A mi gusto", subtitle: "Elige tu color", icon: "paintbrush.pointed.fill", selected: accentMode == "custom") {
                        accentMode = "custom"
                    }
                }
                if accentMode == "custom" {
                    HStack(spacing: 13) {
                        ForEach(["#17A6BB", "#FF811B", "#B573CD", "#4BAE84", "#ED6978"], id: \.self) { value in
                            Button { accentHex = value } label: {
                                Circle()
                                    .fill(SYNApplePalette52.parseHex(value))
                                    .frame(width: 27, height: 27)
                                    .overlay(Circle().strokeBorder(.white.opacity(0.9), lineWidth: 2))
                                    .overlay {
                                        if accentHex.uppercased() == value {
                                            Image(systemName: "checkmark")
                                                .font(.system(size: 10, weight: .bold))
                                                .foregroundStyle(.white)
                                        }
                                    }
                            }
                            .buttonStyle(.plain)
                            .help(value)
                        }
                        Spacer()
                        ColorPicker("Otro color", selection: Binding(
                            get: { SYNApplePalette52.parseHex(accentHex) },
                            set: { accentHex = SYNApplePalette52.hex($0) ?? accentHex }
                        ), supportsOpacity: false)
                        .font(.system(size: 12))
                    }
                    .padding(.vertical, 6)
                }
            }
            synSettingsBlock78("Guía de televisión") {
                Button { synEPGGlass78.toggle() } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "square.on.square.dashed")
                            .font(.system(size: 23))
                            .foregroundStyle(.teal)
                            .frame(width: 43, height: 43)
                            .background(Color.teal.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Pastillas con cristal").font(.system(size: 14, weight: .semibold))
                            Text("Un toque de transparencia en la EPG")
                                .font(.system(size: 11)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: synEPGGlass78 ? "checkmark.circle.fill" : "circle")
                            .font(.system(size: 23))
                            .foregroundStyle(synEPGGlass78 ? .teal : .secondary)
                    }
                }.buttonStyle(.plain)
            }
            synSettingsBlock78("Logos de canales") {
                VStack(spacing: 10) {
                    synSettingsAction7102("Recargar logos del proveedor",
                        subtitle: synLogoRefreshMessage96,
                        icon: "arrow.clockwise.circle.fill", tint: .teal) {
                        synReloadProviderLogos96()
                    }
                    synSettingsAction7102("Personalizar logos", subtitle: "Haz clic derecho sobre un canal para cambiar su imagen", icon: "photo.on.rectangle.angled", tint: .teal) {
                        synSettingsVisible58 = false
                        state.section = .tv
                    }
                }
            }
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 12) {
            Image(colors.dark ? "SYNLogoLight" : "SYNLogoDark")
                .resizable()
                .scaledToFit()
                .frame(width: 228, height: 108, alignment: .center)
                .accessibilityLabel("SYN")
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.top, 8)
                .padding(.bottom, 8)


            VStack(spacing: 3) {
                ForEach(SYNState.Section.allCases.sorted { synSidebarRank($0) < synSidebarRank($1) }) { section in
                    Button {
                        synVisibleLimit = 100
                        synLibraryPlayer76 = false
                        synLibraryEpisodesOpen76 = false
                        state.section = section
                        query = ""; state.query = ""
                    } label: {
                        Label(section.rawValue, systemImage: section.symbol)
                            .font(.system(size: 14, weight: state.section == section ? .semibold : .medium))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 12).padding(.vertical, 9)
                                                    .modifier(SYNSidebarSelection78(selected: state.section == section))
                    }
                    .buttonStyle(.plain)
                }
            }.padding(.horizontal, 9)
            Divider()
                .opacity(0.35)
                .padding(.horizontal, 18)
                .padding(.vertical, 4)
            Button {
                synSettingsVisible58 = true
            } label: {
                Label("Ajustes", systemImage: "gearshape")
                    .font(.system(size: 13, weight: .medium))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .padding(.horizontal, 9)
            Spacer()
            // SYN_72_REC_DISCRETO: estado persistente, sin cubrir el vídeo.
            if synRecordingCount71 > 0 || synDVRRetryingCount803 > 0 || !synNotice71.isEmpty {
                VStack(alignment: .leading, spacing: 7) {
                    HStack(spacing: 7) {
                        Image(systemName: synRecordingCount71 > 0 ? "record.circle.fill" : (synDVRRetryingCount803 > 0 ? "arrow.clockwise.circle.fill" : "exclamationmark.circle.fill"))
                            .foregroundStyle(synRecordingCount71 > 0 ? Color.red : Color.orange)
                        Text(synRecordingCount71 > 0 ? "REC · \(synRecordingCount71) activa(s)" : (synDVRRetryingCount803 > 0 ? "DVR · Reconectando" : "Aviso de grabación"))
                            .font(.system(size: 11, weight: .semibold))
                            .lineLimit(1)
                        Spacer(minLength: 2)
                        Button { state.section = .dvr } label: {
                            Image(systemName: "arrow.up.right.square")
                        }
                        .buttonStyle(.plain)
                        .help("Abrir DVR")
                    }
                    if !synNotice71.isEmpty {
                        HStack(alignment: .top, spacing: 5) {
                            Text(synNotice71)
                                .font(.system(size: 10))
                                .foregroundStyle(colors.muted)
                                .fixedSize(horizontal: false, vertical: true)
                            Button { synNotice71 = "" } label: {
                                Image(systemName: "xmark.circle.fill")
                            }
                            .buttonStyle(.plain)
                            .help("Descartar aviso")
                        }
                    }
                }
                .padding(10)
                .background(colors.surface, in: RoundedRectangle(cornerRadius: 11))
                .padding(.horizontal, 9)
                .accessibilityElement(children: .contain)
            }
            // SYN_PROFILE_FOOTER_782: el avatar es una vista independiente.
            // Un Menu borderless no garantiza dibujar una etiqueta compleja.
            VStack(spacing: 10) {
                SYNProfileAvatar78(
                    name: synM3UProfile79?.name ?? state.selectedProfile?.name ?? "Nuevo perfil",
                    size: 64
                )
                .frame(width: 64, height: 64)
                .accessibilityHidden(true)

                Menu {
                    ForEach(profiles.profiles) { profile in
                        Button {
                            synActiveM3UID79 = ""
                            synM3UPlaying79 = nil
                            lastProfileID = profile.id.uuidString
                            state.select(profile)
                        } label: {
                            Label(profile.name, systemImage: "person.crop.circle")
                        }
                    }
                    if !synM3UStore79.profiles.isEmpty {
                        Divider()
                        ForEach(synM3UStore79.profiles) { playlist in
                            Button {
                                synM3USelect79(playlist)
                            } label: {
                                Label(playlist.name, systemImage: "list.bullet.rectangle")
                            }
                        }
                    }
                    Divider()
                    Button("Añadir fuente…") { synProfileTypePicker79 = true }
                    if let activeM3U = synM3UProfile79 {
                        Button("Editar guía XMLTV…") { synM3UEditGuide79 = activeM3U }
                        Button("Eliminar perfil M3U…", role: .destructive) { synM3UDeleteID79 = activeM3U.id }
                    }
                } label: {
                    HStack(spacing: 6) {
                        Text(synM3UProfile79?.name ?? state.selectedProfile?.name ?? "Seleccionar perfil")
                            .font(.system(size: 13, weight: .semibold))
                            .lineLimit(1)
                        Image(systemName: "chevron.up.chevron.down")
                            .font(.system(size: 9, weight: .medium))
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .contentShape(Rectangle())
                }
                .menuStyle(.borderlessButton)
                .help("Cambiar perfil")

                Button {
                    synProfileTypePicker79 = true
                } label: {
                    Label("Añadir perfil", systemImage: "plus")
                        .font(.system(size: 13, weight: .semibold))
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .contentShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
                .foregroundStyle(colors.foreground)
                .background {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(colors.accent.opacity(0.18))
                }
                .overlay {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(colors.accent.opacity(0.45), lineWidth: 1)
                        .allowsHitTesting(false)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 14)
            .padding(.top, 8)
            .padding(.bottom, 28)

        }
        .foregroundStyle(colors.foreground)
        .background(.ultraThinMaterial)
    }

    private var channelColumn: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(state.section.rawValue).font(.system(size: 22, weight: .semibold))

                    Spacer()
                    Button { state.loadCurrentSection() } label: { Image(systemName: "arrow.clockwise") }
                        .buttonStyle(.plain)
                        .disabled(state.selectedProfile == nil || state.busy)
                }
                if state.selectedProfile != nil && state.section != .dvr {
                    TextField("Buscar", text: $state.query)
                        .textFieldStyle(.roundedBorder)
                    Menu {
                        Button("Todas las categorías") { state.chosenCategory = ""; synVisibleLimit = 100 }
                        Divider()
                        ForEach(state.categories) { category in
                            Button(category.categoryName) { state.chosenCategory = category.id; synVisibleLimit = 100 }
                        }
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "line.3.horizontal.decrease.circle")
                            Text(state.categories.first(where: { $0.id == state.chosenCategory })?.categoryName ?? "Todas las categorías")
                                .lineLimit(1)
                            Spacer()
                            Image(systemName: "chevron.down")
                        }
                        .font(.system(size: 12))
                        .padding(8).background(colors.surface, in: RoundedRectangle(cornerRadius: 7))
                    }.menuStyle(.borderlessButton)
                }
            }
            .padding(16)
            Divider().opacity(0.3)

            if state.selectedProfile == nil {
                ContentUnavailableView("Tu televisión empieza aquí", systemImage: "network",
                    description: Text("Conecta un proveedor Xtream o añade una lista M3U para comenzar."))
                Button("Añadir fuente") { synProfileTypePicker79 = true }.buttonStyle(.borderedProminent)
            } else if state.section == .dvr {
                VStack(alignment: .leading, spacing: 12) {
                    Text("DVR activo").font(.headline)
                    Text("Sintoniza un canal y utiliza la zona DVR junto al reproductor.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if synDVR53.isRecording {
                        Label("Grabando: \(synDVR53.channel)", systemImage: "record.circle.fill")
                            .foregroundStyle(.red)
                    }
                }.padding(16)
            } else if state.busy {
                ProgressView("Consultando Xtream…").frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    switch state.section {
                    case .tv, .favorites, .epg:
                        ForEach(
                            Array(synDisplayedChannels.prefix(synVisibleLimit))
                        ) { ch in
                            HStack(spacing: 6) {
                                HStack(spacing: 9) {
                                    synChannelPill(ch)
                                        .contextMenu { synLogoMenu(ch) }
                                    Text(synCleanChannelName(ch.name))
                                        .font(.system(size: 12, weight: .medium)).lineLimit(1)
                                    Spacer(minLength: 0)
                                }
                                .padding(.horizontal, 7)
                                .padding(.vertical, 5)
                                .contentShape(Rectangle())
                                // Un clic SELECCIONA. Doble clic reproduce, sin disparar el gesto sencillo.
                                .gesture(TapGesture(count: 2)
                                    .exclusively(before: TapGesture(count: 1))
                                    .onEnded { gesture in
                                        switch gesture {
                                        case .first:
                                            synSelectedChannel75 = ch.id
                                            state.tune(ch)
                                        case .second:
                                            synSelectedChannel75 = ch.id
                                        }
                                    })
                                .background(
                                    synSelectedChannel75 == ch.id ? colors.accent.opacity(0.22) : Color.clear,
                                    in: RoundedRectangle(cornerRadius: 9, style: .continuous)
                                )
                                .help("Un clic selecciona · Doble clic reproduce")
                                Button { state.toggleFavorite(ch) } label: {
                                    Image(systemName: state.favorites.contains(state.favoriteKey(ch.id)) ? "heart.fill" : "heart")
                                        .foregroundStyle(
                                            state.favorites.contains(state.favoriteKey(ch.id))
                                            ? colors.accent : colors.muted
                                        )
                                }.buttonStyle(.plain).help("Favorito")
                            }
                            .padding(.vertical, 4)
                            .listRowBackground(synSelectedChannel75 == ch.id ? colors.accent.opacity(0.14) : Color.clear)
                            .onAppear {
                                guard ch.id == synDisplayedChannels
                                    .prefix(synVisibleLimit)
                                    .last?.id else { return }

                                if synVisibleLimit < synDisplayedChannels.count {
                                    synVisibleLimit += 100
                                }
                            }
                        }
                    case .movies:
                        ForEach(state.visibleMovies) { film in
                            Button { state.tune(film) } label: {
                                HStack(spacing: 9) {
                                    channelAvatar(film.name, image: film.streamIcon)
                                    Text(film.name).font(.system(size: 12)).lineLimit(2)
                                }.padding(.vertical, 4)
                            }.buttonStyle(.plain)
                        }
                    case .series:
                        ForEach(state.visibleShows) { show in
                            Button { state.loadEpisodes(show) } label: {
                                HStack(spacing: 9) {
                                    channelAvatar(show.name, image: show.cover)
                                    Text(show.name).font(.system(size: 12)).lineLimit(2)
                                    Spacer()
                                    Image(systemName: "chevron.right").font(.system(size: 9))
                                }.padding(.vertical, 4)
                            }.buttonStyle(.plain)
                        }
                    case .dvr: EmptyView()
                    }
                }
                .listStyle(.plain).scrollContentBackground(.hidden).scrollIndicators(.automatic)
            }
            HStack {
                Text(state.status).lineLimit(1)
                Spacer()
            }.font(.system(size: 10)).foregroundStyle(colors.muted)
                .padding(.horizontal, 14).padding(.vertical, 9)
        }
        .foregroundStyle(colors.foreground)
        .background(colors.panel)
    }

    private func channelAvatar(_ title: String, image: String?) -> some View {
        HStack {
            if let image, let url = URL(string: image), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                AsyncImage(url: url) { value in
                    if let img = value.image { img.resizable().scaledToFit() }
                    else { Text(String(title.prefix(3)).uppercased()).font(.system(size: 9, weight: .bold)) }
                }.frame(width: 62, height: 34)
            } else {
                Text(String(title.prefix(3)).uppercased()).font(.system(size: 9, weight: .bold))
                    .frame(width: 62, height: 34)
            }
        }
        .frame(width: 74, height: 42)
        .background(colors.surface, in: RoundedRectangle(cornerRadius: 7))
    }

    // SYN_GTK_PILLS_42 — logos personalizados por perfil, URL o archivo local.
    private func synLogoKey(_ ch: LiveStream) -> String {
        (state.selectedProfile?.id.uuidString ?? "-") + ":" + ch.id
    }

    // SYN_CHANNEL_ART_43: identidad cromática de la imagen real.
    private func synChannelPill(_ ch: LiveStream) -> some View {
        // SYN_XTREAM_LOGO_RECOVERY_591: conserva las personalizaciones, pero
        // siempre permite recuperar el logo original ante una URL rota.
        let original = (ch.streamIcon ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let custom = (synLogoOverrides[synLogoKey(ch)] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let chosen = custom.isEmpty ? original : custom
        return SYNChannelArtworkPill(name: ch.name, source: chosen,
                                     fallbackSource: custom.isEmpty ? "" : original)
            // Recrea solo la vista del logo al pedir recarga, no el canal ni sus datos.
            .id(synLogoReloadRevision96)
            .frame(width: 106, height: 43)
            .help("\(ch.name) · Clic derecho para cambiar logo")
    }

    @ViewBuilder private func synLogoMenu(_ ch: LiveStream) -> some View {
        Button("Cambiar logo por URL…", systemImage: "link") {
            synLogoEditingKey = synLogoKey(ch)
            synLogoDraft = synLogoOverrides[synLogoEditingKey] ?? ""
            synLogoURLVisible = true
        }
        Button("Elegir imagen local…", systemImage: "photo") {
            synChooseLocalLogo(ch)
        }
        Button("Restaurar logo Xtream", systemImage: "arrow.uturn.backward") {
            synLogoOverrides.removeValue(forKey: synLogoKey(ch))
            synPersistLogos()
        }
    }

    // SYN_PROVIDER_LOGO_REFRESH_96: no se llama a la carga del perfil ni al DVR.
    private func synReloadProviderLogos96() {
        // Solo las URLs originales publicadas por las fuentes; nunca el override
        // del usuario ni el contenido de SYNNative/ChannelLogos.
        let xtreamOriginals = (state.channels + synCatalog74).compactMap { $0.streamIcon }
        let m3uOriginals = synM3UStore79.channels.compactMap { $0.logo }
        let count = SYNChannelImageStore.invalidateProviderImages96(xtreamOriginals + m3uOriginals)
        if count > 0 {
            synLogoReloadRevision96 &+= 1
            synLogoRefreshMessage96 = "Solicitada la recarga de \(count) logos. Se descargarán al mostrar los canales; tus personalizaciones siguen intactas."
        } else {
            synLogoRefreshMessage96 = "No hay URLs de logos cargadas. Abre TV y vuelve a intentarlo. No se ha modificado ningún dato."
        }
    }

    private func synPersistLogos() {
        UserDefaults.standard.set(synLogoOverrides, forKey: "syn.native.logoOverrides")
    }

    private func synSaveLogoURL() {
        let value = synLogoDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: value), ["https", "http"].contains(url.scheme?.lowercased() ?? ""),
              !synLogoEditingKey.isEmpty else { return }
        synLogoOverrides[synLogoEditingKey] = value
        synPersistLogos()
    }

    private func synChooseLocalLogo(_ ch: LiveStream) {
        let picker = NSOpenPanel()
        picker.allowedContentTypes = [.png, .jpeg, .heic, .gif, .webP]
        picker.canChooseDirectories = false
        picker.canChooseFiles = true
        picker.allowsMultipleSelection = false
        guard picker.runModal() == .OK, let source = picker.url else { return }
        do {
            let folder = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("SYNNative/ChannelLogos", isDirectory: true)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let name = UUID().uuidString + "." + source.pathExtension.lowercased()
            let dest = folder.appendingPathComponent(name)
            try FileManager.default.copyItem(at: source, to: dest)
            synLogoOverrides[synLogoKey(ch)] = dest.path
            synPersistLogos()
        } catch {
            NSLog("SYN: no se pudo guardar imagen local: %@", error.localizedDescription)
        }
    }

    // SYN_GTK_PORT_31 — Reordenación conservando el enum existente.
    private func synSidebarRank(_ section: SYNState.Section) -> Int {
        switch section {
        case .tv: return 0
        case .epg: return 1
        case .series: return 2
        case .movies: return 3
        case .dvr: return 4
        case .favorites: return 5
        }
    }

    private var synEPGTimeline: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text("CANAL").frame(width: 100, alignment: .leading)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 0) {
                        ForEach(0..<8, id: \.self) { offset in
                            Text(Date.now.addingTimeInterval(Double(offset) * 1800), format: .dateTime.hour().minute())
                                .frame(width: 154, alignment: .leading)
                        }
                    }
                }
            }
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(colors.muted)

            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(state.playingTitle).font(.system(size: 11, weight: .semibold)).lineLimit(2)
                    Text("DIRECTO").font(.system(size: 9, weight: .bold))
                        .foregroundStyle(colors.accent)
                }
                .frame(width: 100, height: 73, alignment: .leading)
                ScrollView(.horizontal, showsIndicators: true) {
                    HStack(spacing: 3) {
                        ForEach(Array(state.epg.enumerated()), id: \.offset) { index, item in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(item.start ?? "—")
                                    .font(.system(size: 9, weight: .medium))
                                    .lineLimit(1)
                                Text(item.titleText)
                                    .font(.system(size: 12, weight: .semibold))
                                    .lineLimit(2)
                                Spacer(minLength: 0)
                            }
                            .foregroundStyle(.white)
                            .padding(9)
                            .frame(width: 170, height: 74, alignment: .leading)
                            .modifier(SYNEPGGradient7104(tint: synEPGColor(index), enabled: synEPGGlass78))
                        }
                    }
                }
            }
            Text("Programación del canal seleccionado · desplaza horizontalmente")
                .font(.system(size: 10))
                .foregroundStyle(colors.muted)
        }
    }

    // SYN 7.10.7 — Misma paleta neón para la EPG del canal y la guía multicanal.
    private func synEPGColor(_ index: Int) -> Color {
        synGuideColor(index)
    }

    // SYN_EPG_GRADIENT_7104 — texto blanco sobre pastillas de color oscuro.

    // SYN_NATIVE_EPG_MULTICANAL_32
    private var synGuideChannels: [LiveStream] {
        let inFullGuide = state.section == .epg
        let category = inFullGuide ? synGuideCategory73 : state.chosenCategory
        let text = synGuideSearch73.trimmingCharacters(in: .whitespacesAndNewlines)
        let base = (inFullGuide ? synAvailableChannels74 : state.channels).filter { channel in
            if inFullGuide && synGuideFavorites73 && !state.isFavorite(channel) { return false }
            if !inFullGuide && state.section == .favorites && !state.isFavorite(channel) { return false }
            if !category.isEmpty && channel.categoryID?.value != category { return false }
            if inFullGuide && !text.isEmpty && !channel.name.localizedCaseInsensitiveContains(text) { return false }
            return true
        }
        return Array(base.prefix(synGuideVisibleCount))
    }

    private func synEPGDate(_ input: String?, timestamp: FlexibleID? = nil) -> Date? {
        // SYN_FIX41_TIME: los timestamps Unix son instantes absolutos.
        // Usarlos evita interpretar una hora UTC del proveedor como hora local.
        if let text = timestamp?.value, let number = Double(text), number > 1_000_000_000 {
            return Date(timeIntervalSince1970: number > 10_000_000_000 ? number / 1000 : number)
        }
        guard let input, !input.isEmpty else { return nil }
        for format in ["yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm", "HH:mm"] {
            let df = DateFormatter()
            df.locale = Locale(identifier: "en_US_POSIX")
            df.timeZone = .current
            df.dateFormat = format
            if let date = df.date(from: input) {
                if format == "HH:mm" {
                    let comps = Calendar.current.dateComponents([.hour,.minute], from: date)
                    return Calendar.current.date(bySettingHour: comps.hour ?? 0, minute: comps.minute ?? 0, second: 0, of: Date())
                }
                return date
            }
        }
        return nil
    }

    private var synGuideStart: Date {
        let now = Date()
        let interval: TimeInterval = 1800
        // SYN_NATIVE_EPG_CENTERED_36: reserva 8 horas de pasado.
        // Desplazar la guía no altera el origen ni vuelve a pedir canales.
        return Date(timeIntervalSince1970: floor(now.timeIntervalSince1970 / interval) * interval - 8 * 3600)
    }

    private func synGuideOffset(_ entries: [EPGEntry], _ index: Int) -> CGFloat {
        guard index < entries.count else { return 0 }
        if let date = synEPGDate(entries[index].start, timestamp: entries[index].startTimestamp) {
            return CGFloat(date.timeIntervalSince(synGuideStart) / 60 * 5)
        }
        return CGFloat(index * 180)
    }

    private func synGuideWidth(_ entries: [EPGEntry], _ index: Int) -> CGFloat {
        if index + 1 < entries.count,
           let a = synEPGDate(entries[index].start, timestamp: entries[index].startTimestamp),
           let b = synEPGDate(entries[index + 1].start, timestamp: entries[index + 1].startTimestamp), b > a {
            return CGFloat(min(1440, max(10, b.timeIntervalSince(a) / 60))) * 5
        }
        return 300
    }

    // SYN 7.10.7 — Pigmentos neón, sin alternar tipografía blanca/negra.
    // El modificador ajusta el fondo por contraste; el borde conserva el tono fluor.
    private func synGuideColor(_ index: Int) -> Color {
        switch index % 8 {
        case 0: return Color(red: 1.00, green: 0.11, blue: 0.72) // fucsia eléctrico
        case 1: return Color(red: 0.00, green: 0.91, blue: 0.83) // turquesa fluor
        case 2: return Color(red: 0.61, green: 0.35, blue: 1.00) // violeta neón
        case 3: return Color(red: 0.20, green: 0.50, blue: 1.00) // azul eléctrico
        case 4: return Color(red: 0.74, green: 0.95, blue: 0.12) // lima ácido
        case 5: return Color(red: 1.00, green: 0.30, blue: 0.42) // coral intenso
        case 6: return Color(red: 1.00, green: 0.53, blue: 0.12) // naranja eléctrico
        default: return Color(red: 0.10, green: 0.90, blue: 0.60) // verde menta
        }
    }

    // SYN_EPG_ATOMIC_77 — hasta 8 solicitudes paralelas, resultados publicados juntos.
    // Xtream es la única fuente; no se generan programas imaginarios.
    @MainActor private func synFetchGuide77(_ channels: [LiveStream], client: XtreamClient) async -> [String: [EPGEntry]] {
        let missing = channels.map(\.id).filter { synGuideEntries[$0] == nil }
        var collected: [String: [EPGEntry]] = [:]
        for start in stride(from: 0, to: missing.count, by: 8) {
            if Task.isCancelled { break }
            let groupIDs = Array(missing[start..<min(start + 8, missing.count)])
            let results = await withTaskGroup(of: (String, [EPGEntry]).self, returning: [(String, [EPGEntry])].self) { group in
                for streamID in groupIDs {
                    group.addTask {
                        let full = (try? await client.epgFull(streamID: streamID)) ?? []
                        // Evita una segunda petición cuando Xtream ya ofrece una guía suficiente.
                        let entries = full.count > 2 ? full : ((try? await client.epg(streamID: streamID, limit: 96)) ?? full)
                        return (streamID, entries)
                    }
                }
                var batch: [(String, [EPGEntry])] = []
                for await result in group { batch.append(result) }
                return batch
            }
            for (id, entries) in results { collected[id] = entries }
        }
        for (id, entries) in collected {
            collected[id] = entries.sorted {
                (synEPGDate($0.start, timestamp: $0.startTimestamp) ?? .distantPast) <
                (synEPGDate($1.start, timestamp: $1.startTimestamp) ?? .distantPast)
            }
        }
        return collected
    }

    @MainActor private func synLoadMultiGuide() async {
        let scope = "\(state.selectedProfile?.id.uuidString ?? "-")|\(state.section.rawValue)|\(state.section == .epg ? synGuideCategory73 : state.chosenCategory)|\(state.channels.count)|\(synGuideFavorites73)|\(synGuideSearch73)|\(synGuideVisibleCount)"
        guard scope != synGuideScope, let client = state.client else { return }
        synGuideScope = scope
        let selection = synGuideChannels
        guard selection.contains(where: { synGuideEntries[$0.id] == nil }) else {
            synGuideBusy = false
            return
        }
        synGuideBusy = true
        let updates = await synFetchGuide77(selection, client: client)
        guard !Task.isCancelled, synGuideScope == scope else { return }
        // Un solo cambio de estado para todas las pastillas; no se ven caer fila a fila.
        synGuideEntries.merge(updates) { _, new in new }
        synGuideBusy = false
    }

    @MainActor private func synLoadNextGuidePage77() async {
        guard !synGuideBusy, !synGuideNextPageBusy77, let client = state.client else { return }
        let scope = "\(state.selectedProfile?.id.uuidString ?? "-")|\(state.section.rawValue)|\(state.section == .epg ? synGuideCategory73 : state.chosenCategory)|\(synGuideFavorites73)|\(synGuideSearch73)"
        let source = state.section == .epg ? synAvailableChannels74 : state.channels
        let total = source.filter { item in
            if state.section == .epg {
                if synGuideFavorites73 && !state.isFavorite(item) { return false }
                if !synGuideCategory73.isEmpty && item.categoryID?.value != synGuideCategory73 { return false }
                if !synGuideSearch73.isEmpty && !item.name.localizedCaseInsensitiveContains(synGuideSearch73) { return false }
            } else {
                if state.section == .favorites && !state.isFavorite(item) { return false }
                if !state.chosenCategory.isEmpty && item.categoryID?.value != state.chosenCategory { return false }
            }
            return true
        }
        let next = min(total.count, synGuideVisibleCount + 20)
        guard next > synGuideVisibleCount else { return }
        synGuideNextPageBusy77 = true
        defer { synGuideNextPageBusy77 = false }
        let updates = await synFetchGuide77(Array(total.prefix(next)), client: client)
        let check = "\(state.selectedProfile?.id.uuidString ?? "-")|\(state.section.rawValue)|\(state.section == .epg ? synGuideCategory73 : state.chosenCategory)|\(synGuideFavorites73)|\(synGuideSearch73)"
        guard !Task.isCancelled, check == scope else { return }
        synGuideEntries.merge(updates) { _, new in new }
        // El scroll solo descubre las filas CUANDO sus datos ya se han preparado.
        synGuideVisibleCount = next
    }

    // An empty program list is valid, provided it has been fetched.
    private func synGuidePageReady771(_ channels: [LiveStream]) -> Bool {
        channels.allSatisfy { synGuideEntries[$0.id] != nil }
    }

    // EPG_VIEWCELL_771: independent cell keeps the SwiftUI type checker responsive.
    @ViewBuilder private func synGuideProgrammeCard771(
        item: EPGEntry, entries: [EPGEntry], index: Int, channel: LiveStream
    ) -> some View {
        let x = synGuideOffset(entries, index)
        let w = synGuideWidth(entries, index)
        if x + w > 0 && x < 14550 {
            VStack(alignment: .leading, spacing: 4) {
                Text(synEPGDate(item.start, timestamp: item.startTimestamp) .map { $0.formatted(date: .omitted, time: .shortened) } ?? "—")
                    .font(.system(size: 9))
                    .lineLimit(1)
                if w >= 98 {
                    Text(item.titleText)
                        .font(.system(size: 11, weight: .semibold))
                        .lineLimit(2)
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(.white)
            .padding(7)
            .frame(width: max(28, w - 3), height: SYNResponsiveSplit7106.rowHeight - 2, alignment: .leading)
            .modifier(SYNEPGGradient7104(tint: synGuideColor(index), enabled: synEPGGlass78))
            .modifier(SYNEPGInfoCard(item: item, start: synEPGDate(item.start, timestamp: item.startTimestamp), end: synEPGDate(item.end, timestamp: item.stopTimestamp)))
            .contextMenu {
                Button("Programar grabación…") {
                    guard let begin = synEPGDate(item.start, timestamp: item.startTimestamp),
                          let finish = synEPGDate(item.end, timestamp: item.stopTimestamp),
                          finish > Date(), finish > begin, let client = state.client else {
                        synDVR54Message = "Este programa no tiene un horario válido de inicio y fin."
                        return
                    }
                    do {
                        let link = try client.liveURL(channel)
                        synEPGPending90 = SYNEPGMarginRequest90(url: link, channel: channel.name,
                            title: item.titleText, start: begin, end: finish)
                    } catch { synDVR54Message = "No se pudo preparar la grabación: \(error.localizedDescription)" }
                }
            }
            // SYN_EPG_OFFSET_RESTORE_772: situar la pastilla en su hora real.
            .offset(x: max(0, x))
        }
    }

    private func synGuideChannelRow771(_ channel: LiveStream, isLast: Bool) -> some View {
        Button { state.tune(channel) } label: {
            HStack(spacing: 6) {
                synChannelPill(channel)
                    .contextMenu { synLogoMenu(channel) }
                    .frame(width: 106, height: 43, alignment: .center)
                VStack(alignment: .leading, spacing: 2) {
                    Text(synCleanChannelName(channel.name))
                        .font(.system(size: 10, weight: .medium))
                        .lineLimit(2)
                    if state.isFavorite(channel) {
                        Image(systemName: "heart.fill")
                            .font(.system(size: 9))
                            .foregroundStyle(colors.accent)
                    }
                }
                Spacer(minLength: 0)
            }
            .frame(width: 200, height: SYNResponsiveSplit7106.rowHeight, alignment: .leading)
            .contentShape(Rectangle())
            .background(colors.surface.opacity(0.38), in: RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
        .onAppear {
            guard isLast else { return }
            Task { await synLoadNextGuidePage77() }
        }
    }

    // SYN_NATIVE_EPG_35 — Tabla EPG completa + comparación short EPG
    // SYN_NATIVE_EPG_24H_34 — Horizonte 24 h y EPG ampliada
    // SYN_NATIVE_EPG_GTK_33 — Cabecera temporal y canales fijos como en SYN GTK.
    private var synMultiGuide: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Guía de televisión")
                        .font(.system(size: 14, weight: .bold))
                    Text("Programación en directo")
                        .font(.system(size: 10))
                        .foregroundStyle(colors.muted)
                }
                Spacer()
                if synGuideBusy || synGuideNextPageBusy77 { ProgressView().controlSize(.small) }
                Button {
                    synGuideShiftMinutes -= 60
                } label: { Image(systemName: "chevron.left") }
                .help("Una hora antes")
                Button("Ahora") {
                    synGuideShiftMinutes = 0
                    synGuideFocusRevision += 1
                }
                .help("Centrar la hora actual")
                Button {
                    withAnimation(.easeInOut(duration: 0.22)) {
                        synGuideExpanded7103.toggle()
                    }
                } label: {
                    Label(synGuideExpanded7103 ? "Más vídeo" : "Más EPG",
                          systemImage: synGuideExpanded7103 ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                }
                .help(synGuideExpanded7103 ? "Volver al reproductor grande" : "Dar más espacio a la guía mientras redimensionas")
                Button {
                    synGuideShiftMinutes += 60
                } label: { Image(systemName: "chevron.right") }
                .help("Una hora después")
                Button {
                    synGuideScope = ""
                    synGuideEntries.removeAll()
                    Task { await synLoadMultiGuide() }
                } label: { Image(systemName: "arrow.clockwise") }
                .help("Actualizar programación")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .frame(height: SYNResponsiveSplit7106.headerHeight)

            TimelineView(.periodic(from: .now, by: 30)) { timeline in
                GeometryReader { geometry in
                    let guideHeight = max(152, geometry.size.height)
                    let channels = synGuideChannels
                    // SYN_EPG_VIEWFIX_771: no large if/else enclosing the entire grid.
                    ScrollView(.vertical) {
                        HStack(alignment: .top, spacing: 0) {
                            // Columna de canales fija mientras cambian las horas.
                            LazyVStack(alignment: .leading, spacing: 2) {
                                Text("CANAL")
                                    .font(.system(size: 9, weight: .semibold))
                                    .foregroundStyle(colors.muted)
                                    .frame(height: 28, alignment: .center)
                                ForEach(channels) { channel in
                                    synGuideChannelRow771(channel, isLast: channel.id == channels.last?.id)
                                }
                            }
                            .frame(width: 208)
                            ScrollViewReader { synGuideProxy in
                            ScrollView(.horizontal) {
                                VStack(alignment: .leading, spacing: 2) {
                                    ZStack(alignment: .topLeading) {
                                        ForEach(0..<97, id: \.self) { tick in
                                            Text(synGuideStart.addingTimeInterval(Double(tick) * 1800), format: .dateTime.hour().minute())
                                                .font(.system(size: 10, weight: .medium))
                                                .foregroundStyle(colors.muted)
                                                .position(x: CGFloat(tick * 150) + 23, y: 14)
                                        }
                                        // SYN_EPG_FIX_40: punto de enfoque dentro del contenido.
                                        let focusedTime = timeline.date.addingTimeInterval(Double(synGuideShiftMinutes) * 60)
                                        let focusX = CGFloat(focusedTime.timeIntervalSince(synGuideStart) / 60 * 5)
                                        Color.clear
                                            .frame(width: 2, height: 2)
                                            .position(x: max(2, min(14548, focusX)), y: 12)
                                            .id("syn-guide-focus")
                                    }
                                    .frame(width: 14550, height: 28)
                                    ForEach(channels) { channel in
                                        ZStack(alignment: .topLeading) {
                                            let entries = synGuideEntries[channel.id] ?? []
                                            if entries.isEmpty {
                                                Text(synGuideBusy ? "Cargando programación…" : "Sin programación disponible")
                                                    .font(.system(size: 11))
                                                    .foregroundStyle(colors.muted)
                                                    .padding(12)
                                            }
                                            ForEach(Array(entries.enumerated()), id: \.offset) { index, item in
                                                synGuideProgrammeCard771(item: item, entries: entries, index: index, channel: channel)
                                            }
                                        }
                                        .frame(width: 14550, height: SYNResponsiveSplit7106.rowHeight, alignment: .topLeading)
                                        .background(colors.surface.opacity(0.35), in: RoundedRectangle(cornerRadius: 6))
                                    }
                                }
                                // SYN_FIX41_CENTER: el desplazamiento ocurre en NSScrollView real.
                                .background(SYNMouseDragScrollBridge(
                                    focusX: CGFloat(timeline.date.addingTimeInterval(Double(synGuideShiftMinutes) * 60).timeIntervalSince(synGuideStart) / 60 * 5),
                                    revision: synGuideFocusRevision
                                ))
                                .overlay(alignment: .topLeading) {
                                    let x = CGFloat(timeline.date.timeIntervalSince(synGuideStart) / 60 * 5)
                                    if x >= 0 && x <= 14550 {
                                        VStack(spacing: 0) {
                                            Text(timeline.date, format: .dateTime.hour().minute())
                                                .font(.system(size: 10, weight: .bold, design: .rounded))
                                                .foregroundStyle(.white)
                                                .padding(.horizontal, 7)
                                                .padding(.vertical, 4)
                                                .background(colors.accent, in: Capsule())
                                                .fixedSize()
                                            Rectangle()
                                                .fill(colors.accent)
                                                .frame(width: 3)
                                                .frame(maxHeight: .infinity)
                                        }
                                        .frame(maxHeight: .infinity, alignment: .top)
                                        .offset(x: max(0, x - 20))
                                        .allowsHitTesting(false)
                                    }
                                }
                            }
                            .scrollIndicators(.automatic)
                            .onAppear { synGuideFocusRevision += 1 }
                            .onChange(of: synGuideBusy) { _, busy in
                                if !busy { synGuideFocusRevision += 1 }
                            }
                            .onChange(of: synGuideShiftMinutes) { _, _ in
                                synGuideFocusRevision += 1
                            }
                            }
                        }
                        .padding(2)
                    }
                    .frame(height: guideHeight)
                    .opacity(synGuidePageReady771(channels) ? 1 : 0)
                    .overlay {
                        if !synGuidePageReady771(channels) {
                            VStack(spacing: 10) {
                                ProgressView().controlSize(.regular)
                                Text("Preparando programación…")
                                    .font(.system(size: 12))
                                    .foregroundStyle(colors.muted)
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                        }
                    }
                    .background(colors.surface.opacity(0.20), in: RoundedRectangle(cornerRadius: 9))
                }
            }
            .frame(minHeight: 160, maxHeight: .infinity)
            HStack(spacing: 6) {
                Image(systemName: "clock")
                Text("Desplaza la guía sin cambiar el canal · «Ahora» centra el directo")
                    .lineLimit(1)
            }
            .font(.system(size: 10))
            .foregroundStyle(colors.muted)
            .frame(height: SYNResponsiveSplit7106.footerHeight)
        }
        .onChange(of: state.section) { _, _ in synGuideVisibleCount = 20; synGuideScope = "" }
        .onChange(of: state.chosenCategory) { _, _ in synGuideVisibleCount = 20; synGuideScope = "" }
        .task(id: "\(state.selectedProfile?.id.uuidString ?? "-")|\(state.section.rawValue)|\(state.section == .epg ? synGuideCategory73 : state.chosenCategory)|\(synGuideFavorites73)|\(synGuideSearch73)|\(state.channels.count)|\(synGuideVisibleCount)") {
            await synLoadMultiGuide()
        }
    }

    // SYN_FS_GTK_59: navegar entre canales visibles manteniendo la reproducción.
    private func synFullscreenZap59(_ delta: Int) {
        if let playlist = synM3UProfile79 {
            let channels = synM3UStore79.filtered(profileID: playlist.id)
            guard !channels.isEmpty else { return }
            let current = channels.firstIndex(where: { $0.id == synM3UPlaying79?.id }) ?? (delta > 0 ? -1 : 0)
            synM3UTune79(channels[(current + delta + channels.count) % channels.count])
            return
        }
        let channels = synDisplayedChannels
        guard !channels.isEmpty else { return }
        let current = channels.firstIndex { $0.name == state.playingTitle } ?? (delta > 0 ? -1 : 0)
        let next = (current + delta + channels.count) % channels.count
        state.tune(channels[next])
    }

    // SYN_FULL_CONTENT_70 — real Xtream EPG passed to fullscreen AppKit.
    private func synSchedule70(for channel: LiveStream?) -> (SYNProgram70, SYNProgram70) {
        guard let channel else {
            return (SYNProgram70(title: "", start: nil, end: nil),
                    SYNProgram70(title: "", start: nil, end: nil))
        }
        let entries = synGuideEntries[channel.id] ?? (channel.name == state.playingTitle ? state.epg : [])
        let ordered = entries.sorted {
            (synEPGDate($0.start, timestamp: $0.startTimestamp) ?? .distantPast) <
            (synEPGDate($1.start, timestamp: $1.startTimestamp) ?? .distantPast)
        }
        let now = Date()
        let index = ordered.firstIndex {
            guard let start = synEPGDate($0.start, timestamp: $0.startTimestamp),
                  let end = synEPGDate($0.end, timestamp: $0.stopTimestamp) else { return false }
            return start <= now && now < end
        }
        let nextIndex = index.map { $0 + 1 } ?? ordered.firstIndex {
            (synEPGDate($0.start, timestamp: $0.startTimestamp) ?? .distantPast) > now
        }
        func make(_ item: EPGEntry?) -> SYNProgram70 {
            guard let item else { return SYNProgram70(title: "", start: nil, end: nil) }
            return SYNProgram70(title: item.titleText,
                start: synEPGDate(item.start, timestamp: item.startTimestamp),
                end: synEPGDate(item.end, timestamp: item.stopTimestamp))
        }
        let current = index.flatMap { ordered.indices.contains($0) ? ordered[$0] : nil }
        let next = nextIndex.flatMap { ordered.indices.contains($0) ? ordered[$0] : nil }
        return (make(current), make(next))
    }

    private var synFullscreenGuide70: [SYNGuideChannel70] {
        // IDs válidos de TODOS los canales Xtream; EPG se consulta al aparecer cada fila.
        // No lanzamos miles de peticiones a la vez.
        synAvailableChannels74.map { channel in
            let original = (channel.streamIcon ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            let custom = (synLogoOverrides[synLogoKey(channel)] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            return SYNGuideChannel70(id: channel.id, name: synCleanChannelName(channel.name),
                now: "", next: "", isFavorite: state.isFavorite(channel),
                category: state.categories.first(where: { $0.id == channel.categoryID?.value })?.categoryName ?? "Sin categoría",
                logo: custom.isEmpty ? original : custom,
                fallbackLogo: custom.isEmpty ? "" : original)
        }
    }

    private func synAskM3UEPG90(_ channel: SYNM3UChannel79, _ program: SYNM3UProgramme79) {
        guard program.end > Date(), program.end > program.start else {
            synDVR54Message = "Este programa no tiene un horario válido para programar."; return
        }
        synEPGPending90 = SYNEPGMarginRequest90(url: channel.stream, channel: channel.name,
            title: program.title, start: program.start, end: program.end)
    }

    // SYN_GUIDE_DVR_73: una ÚNICA pantalla de guía, accesible por barra lateral y fullscreen.
    private var synFullGuide73: some View {
        HStack(alignment: .top, spacing: 0) {
            VStack(alignment: .leading, spacing: 6) {
                Button {
                    synGuideFavorites73 = false
                    synGuideCategory73 = ""
                    synGuideVisibleCount = 20
                    synGuideScope = ""
                } label: {
                    Label("Todas las categorías", systemImage: "square.grid.2x2")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                Button {
                    synGuideFavorites73 = true
                    synGuideCategory73 = ""
                    synGuideVisibleCount = 20
                    synGuideScope = ""
                } label: {
                    Label("Favoritos", systemImage: "heart")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                Divider().padding(.vertical, 4)
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(state.categories) { category in
                            Button {
                                synGuideCategory73 = category.id
                                synGuideFavorites73 = false
                                synGuideVisibleCount = 20
                                synGuideScope = ""
                            } label: {
                                Text(category.categoryName)
                                    .lineLimit(2)
                                    .font(.system(size: 11, weight: .medium))
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 5)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .buttonStyle(.plain)
            .padding(12)
            .frame(width: 174)
            .background(colors.panel)
            Divider()
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Guía de televisión").font(.system(size: 20, weight: .semibold))
                        Text("Programación por canales y horarios")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 12)
                    TextField("Buscar canal…", text: $synGuideSearch73)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 200)
                        .onChange(of: synGuideSearch73) { _, _ in
                            synGuideVisibleCount = 20
                            synGuideScope = ""
                        }
                    Button("Cerrar") { state.section = .tv }
                        .help("Volver a televisión")
                }
                .padding(.horizontal, 10)
                .padding(.top, 10)
                synMultiGuide
                    .padding(.horizontal, 7)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .background(colors.background)
        }
        .foregroundStyle(colors.foreground)
        .task { if synCatalog74.isEmpty { await synLoadCatalog74() } }
    }

    // SYN_RECORDING_PANEL_95: misma interfaz principal de SYN.
    // En tamaño normal hay marco 16:9 y controles de archivo; en fullscreen,
    // solo vídeo y controles de reproducción (nunca canales ni EPG).
    private var synRecordingPanel95: some View {
        VStack(spacing: 0) {
            if !synRecordingFullscreen95 {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Grabación · SYN DVR")
                            .font(.system(size: 15, weight: .semibold))
                        Text(synRecording94.file?.deletingPathExtension().lastPathComponent ?? "")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    Spacer(minLength: 8)
                    Button(action: synCloseRecording95) {
                        Label("Volver a DVR", systemImage: "chevron.left")
                    }
                    .buttonStyle(.bordered)
                    .keyboardShortcut(.cancelAction)
                }
                .padding(.horizontal, 16)
                .padding(.top, 14)
                .padding(.bottom, 12)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
            if let video = synRecording94.file {
                GeometryReader { bounds in
                    SYNRecordingPlayback93(file: video, fullscreen: synRecordingFullscreen95)
                        .id(video.path)
                        // Mini 16:9 con marco; fullscreen ocupa toda el área.
                        // La misma instancia VLC conserva la posición al cambiar de modo.
                        .frame(width: bounds.size.width,
                               height: synRecordingFullscreen95
                                   ? bounds.size.height
                                   : min(bounds.size.height, bounds.size.width * 9.0 / 16.0))
                        .background(Color.black)
                        .clipShape(RoundedRectangle(cornerRadius: synRecordingFullscreen95 ? 0 : 15,
                                                    style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: synRecordingFullscreen95 ? 0 : 15,
                                             style: .continuous)
                                .stroke(Color.primary.opacity(synRecordingFullscreen95 ? 0 : 0.20), lineWidth: 1)
                                .allowsHitTesting(false)
                        }
                }
                .padding(.horizontal, synRecordingFullscreen95 ? 0 : 12)
            }
            if !synRecordingFullscreen95 { Spacer(minLength: 0) }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        // SYN_RECORDING_ZOOM_99: frame/padding/radio de esquina animados juntos.
        // Zoom suave pero sin escalar la superficie VLCKit por separado.
        .animation(.easeInOut(duration: 0.36), value: synRecordingFullscreen95)
        .background(synRecordingFullscreen95 ? Color.black : colors.background)
    }

    private func synCloseRecording95() {
        if synRecordingFullscreen95 {
            SYNRecordingWindow93.shared.toggleFullscreen()
        }
        synRecording94.close()
        state.section = .dvr
        synDVR53.refresh()
    }

    private var detailColumn: some View {
        GeometryReader { synAvailableArea7106 in
        let synIsTVGuide7106 = state.section == .tv || state.section == .favorites
        let synSplit7106 = SYNResponsiveSplit7106(
            size: synAvailableArea7106.size,
            expanded: synGuideExpanded7103)
        VStack(spacing: 0) {
            // SYN_623_VIDEO_PRIORITARIO: sin rótulo de canal ni texto del motor.
            // El contenido real de programación se consulta en la EPG.
            ZStack {
                Rectangle().fill(Color.black)
                VLCPlayerView(url: synM3UProfile79 == nil ? state.playingURL : synM3UPlaying79?.stream,
                    channelTitle: synM3UProfile79 == nil ? state.playingTitle : (synM3UPlaying79?.name ?? "Selecciona un canal"),
                    onPreviousChannel: { synFullscreenZap59(-1) },
                    onNextChannel: { synFullscreenZap59(1) },
                    onOpenGuide: { state.section = .epg },
                    nowProgram70: synM3UProfile79 == nil ? synSchedule70(for: state.channels.first(where: { $0.name == state.playingTitle })).0 : synM3UNowNext79.0,
                    nextProgram70: synM3UProfile79 == nil ? synSchedule70(for: state.channels.first(where: { $0.name == state.playingTitle })).1 : synM3UNowNext79.1,
                    guideChannels70: synM3UProfile79 == nil ? synFullscreenGuide70 : synM3UStore79.channels.map { ch in
                        SYNGuideChannel70(id: ch.id, name: ch.name, now: "", next: "", isFavorite: false,
                            category: ch.group, logo: ch.logo ?? "")
                    },
                    tune70: { id in
                        if synM3UProfile79 != nil {
                            if let channel = synM3UStore79.channels.first(where: { $0.id == id }) { synM3UTune79(channel) }
                        } else if let channel = synAvailableChannels74.first(where: { $0.id == id }) {
                            state.tune(channel)
                        }
                    },
                    refreshGuide70: {
                        if let playlist = synM3UProfile79 { Task { await synM3UStore79.load(playlist) } }
                        else { Task { await synLoadCatalog74() } }
                    },
                    loadGuide74: { id in
                        if synM3UProfile79 != nil {
                            guard let channel = synM3UStore79.channels.first(where: { $0.id == id }) else { return [] }
                            return synM3UStore79.channelGuide(channel).map {
                                SYNGuideProgramme74(title: $0.title, start: $0.start, end: $0.end)
                            }
                        }
                        guard let client = state.client else { return [] }
                        let compact: [EPGEntry]
                        if let cached = synGuideEntries[id] {
                            compact = cached
                        } else {
                            let full = (try? await client.epgFull(streamID: id)) ?? []
                            compact = full.count > 2 ? full : ((try? await client.epg(streamID: id, limit: 70)) ?? full)
                            // No se muta ContentView desde el overlay fullscreen:
                            // reconfigurar NSHostingView en cada fila reiniciaría su estado.
                        }
                        return compact.compactMap { item -> SYNGuideProgramme74? in
                            guard let from = synEPGDate(item.start, timestamp: item.startTimestamp),
                                  let to = synEPGDate(item.end, timestamp: item.stopTimestamp), to > from else { return nil }
                            return SYNGuideProgramme74(title: item.titleText, start: from, end: to)
                        }
                    }, scheduleGuide70: { channelID, title, start, end in
                        let source: URL
                        let channelName: String
                        if synM3UProfile79 != nil {
                            guard let channel = synM3UStore79.channels.first(where: { $0.id == channelID }) else {
                                throw NSError(domain: "SYN EPG", code: 90,
                                    userInfo: [NSLocalizedDescriptionKey:"No se encuentra el canal M3U."])
                            }
                            source = channel.stream
                            channelName = channel.name
                        } else {
                            guard let channel = synAvailableChannels74.first(where: { $0.id == channelID }),
                                  let client = state.client else {
                                throw NSError(domain: "SYN EPG", code: 90,
                                    userInfo: [NSLocalizedDescriptionKey:"No se encuentra el canal Xtream."])
                            }
                            source = try client.liveURL(channel)
                            channelName = channel.name
                        }
                        try SYNBackgroundDVR54.add(url: source, channel: channelName, title: title,
                            start: start, end: end, epg: true)
                        synDVR54Jobs = SYNBackgroundDVR54.list()
                        synDVR54Message = "Grabación programada: " + title
                    }) // SYN_ALPHA27_APPLETV
                if (synM3UProfile79 == nil ? state.playingURL : synM3UPlaying79?.stream) == nil {
                    VStack(spacing: 10) {
                        Image(systemName: "play.rectangle.fill").font(.system(size: 49))
                        Text("Selecciona un canal, película o episodio")
                        #if !canImport(VLCKit)
                        Text("Para habilitar VLC: ejecuta 00_ABRIR_EN_XCODE.command")
                            .font(.caption).foregroundStyle(.orange)
                        #endif
                    }.foregroundStyle(.white.opacity(0.8))
                }
            }
            .aspectRatio(16/9, contentMode: .fit)
            .frame(height: synIsTVGuide7106 ? synSplit7106.playerHeight : nil)
            .frame(maxHeight: state.section == .dvr ? 205 : .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .compositingGroup()
            .padding(.horizontal, 3)

            if state.section == .dvr {
                synDVRGTK55.frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if state.section == .series, let chosenShow = state.chosenShow {
                VStack(alignment: .leading, spacing: 9) {
                    Text("Episodios de \(chosenShow.name)").font(.headline)
                    if state.episodes.isEmpty { Text("Cargando episodios o sin datos").font(.caption).foregroundStyle(colors.muted) }
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 6) {
                            ForEach(state.episodes) { ep in
                                Button { state.tune(ep) } label: {
                                    HStack {
                                        Image(systemName: "play.circle")
                                        Text(ep.title ?? "Episodio \(ep.episodeNum?.value ?? "?")")
                                        Spacer()
                                    }.padding(9).background(colors.surface, in: RoundedRectangle(cornerRadius: 7))
                                }.buttonStyle(.plain)
                            }
                        }
                    }.frame(maxHeight: 195)
                }.padding(.horizontal, 19).padding(.top, 15)
             } else if state.section == .tv || state.section == .favorites {
                if let playlist = synM3UProfile79 {
                    SYNM3UGuide79(store: synM3UStore79, profile: playlist, onTune: synM3UTune79,
                                  compactRows7106: synSplit7106.rows, onScheduleEPG90: synAskM3UEPG90)
                        .frame(height: synSplit7106.guideHeight, alignment: .top)
                } else {
                synMultiGuide
                    // El margen exterior (24 pt) queda fuera del área de la tabla.
                    .frame(height: synSplit7106.guideHeight - 24, alignment: .top)
                    .padding(8)
                    .background(colors.surface.opacity(0.30), in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(colors.accent.opacity(0.30), lineWidth: 1))
                    .padding(.horizontal, 10)
                    .padding(.top, 8)
                }
            } else {
                Spacer(minLength: 1)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .foregroundStyle(colors.foreground)
        .background(colors.background)
        .overlay {
            // El mismo VLCPlayerView sigue montado por debajo de la cartelera.
            if (state.section == .movies || state.section == .series) && !synLibraryPlayer76 {
                synLibraryGallery76
            }
        }
        .overlay(alignment: .topLeading) {
            if (state.section == .movies || state.section == .series) && synLibraryPlayer76 {
                Button {
                    synLibraryPlayer76 = false
                } label: {
                    Label("Volver a cartelera", systemImage: "chevron.left")
                }
                .buttonStyle(.borderedProminent)
                .padding(18)
            }
        }
        .sheet(isPresented: $synLibraryEpisodesOpen76) {
            synLibraryEpisodesSheet76
        }
        } // GeometryReader: el vídeo y la guía siguen el tamaño de la ventana.
    }

    // SYN 7.6: la sección Cine/Series usa el catálogo existente de Xtream,
    // sin nuevas consultas ni cambios en la gestión de credenciales.
    private var synLibraryItems76: [SYNPosterItem76] {
        var names: [String: String] = [:]
        for category in state.categories { names[category.id] = category.categoryName }
        if state.section == .movies {
            return state.visibleMovies.map { movie in
                let id = movie.categoryID?.value ?? ""
                return SYNPosterItem76(id: movie.id, title: movie.name,
                    posterURL: movie.streamIcon, categoryID: id,
                    categoryName: names[id] ?? "Película")
            }
        }
        return state.visibleShows.map { show in
            let id = show.categoryID?.value ?? ""
            return SYNPosterItem76(id: show.id, title: show.name,
                posterURL: show.cover, categoryID: id,
                categoryName: names[id] ?? "Serie")
        }
    }

    private var synLibraryGallery76: some View {
        SYNPosterGallery76(
            series: state.section == .series,
            items: synLibraryItems76,
            categories: state.categories.map { SYNPosterCategory76(id: $0.id, name: $0.categoryName) },
            query: $state.query,
            categoryID: $state.chosenCategory,
            onBack: {
                state.section = .tv
                state.query = ""
                state.chosenCategory = ""
            },
            onOpen: { id in
                if state.section == .movies,
                   let movie = state.visibleMovies.first(where: { $0.id == id }) {
                    state.tune(movie)
                    synLibraryPlayer76 = true
                } else if state.section == .series,
                          let show = state.visibleShows.first(where: { $0.id == id }) {
                    state.loadEpisodes(show)
                    synLibraryEpisodesOpen76 = true
                }
            }
        )
    }

    private var synLibraryEpisodesSheet76: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(state.chosenShow?.name ?? "Episodios")
                        .font(.title2.weight(.semibold))
                    Text("Selecciona un episodio para reproducir")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Cerrar") { synLibraryEpisodesOpen76 = false }
            }
            Divider()
            if state.episodes.isEmpty {
                ContentUnavailableView("Cargando episodios o sin datos", systemImage: "play.rectangle")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 7) {
                        ForEach(state.episodes) { episode in
                            Button {
                                state.tune(episode)
                                synLibraryPlayer76 = true
                                synLibraryEpisodesOpen76 = false
                            } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: "play.circle.fill").font(.title3)
                                    Text(episode.title ?? "Episodio \(episode.episodeNum?.value ?? "—")")
                                        .lineLimit(2)
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                }
                                .padding(10)
                                .background(Color(nsColor: .controlBackgroundColor),
                                            in: RoundedRectangle(cornerRadius: 10))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
        .padding(24)
        .frame(minWidth: 530, minHeight: 440)
    }

    // SYN_FIX74_CATALOG: canal que está en el catálogo completo, no solo en la pestaña TV.
    private var synAvailableChannels74: [LiveStream] {
        synCatalog74.isEmpty ? state.channels : synCatalog74
    }
    private var synSelectedDVRChannel74: LiveStream? {
        synAvailableChannels74.first(where: { $0.id == synDVR55ChannelID })
    }
    @MainActor private func synLoadCatalog74() async {
        guard let client = state.client else {
            synCatalogError74 = "Todavía no hay una conexión Xtream activa."
            return
        }
        if synCatalogLoading74 { return }
        synCatalogLoading74 = true
        synCatalogError74 = ""
        defer { synCatalogLoading74 = false }
        do {
            let catalog = try await client.liveStreams() // get_live_streams SIN category_id
            synCatalog74 = catalog
            if catalog.isEmpty { synCatalogError74 = "El servidor no devolvió canales de TV." }
        } catch {
            synCatalogError74 = "Error al cargar canales: " + error.localizedDescription
        }
    }

    // SYN_DVR_GTK_55 — Diseño de dos columnas de la aplicación GTK original.
    // Selector DVR 7.3: evita el Picker de miles de elementos que no permite elegir.
    private var synDVRPickerResults73: [LiveStream] {
        let term = synDVRSearch73.trimmingCharacters(in: .whitespacesAndNewlines)
        return Array(synAvailableChannels74.lazy.filter {
            term.isEmpty || $0.name.localizedStandardContains(term)
        }.prefix(250))
    }

    private var synDVRPickerSheet73: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Seleccionar canal para grabar").font(.title2.weight(.semibold))
                Spacer()
                Button("Cerrar") { synDVRPickerOpen73 = false }
            }
            TextField("Buscar entre los canales Xtream…", text: $synDVRSearch73)
                .textFieldStyle(.roundedBorder)
            HStack(spacing: 8) {
                if synCatalogLoading74 { ProgressView().controlSize(.small) }
                Text("\(synDVRPickerResults73.count) de \(synAvailableChannels74.count) canales · busca por nombre")
                if !synCatalogLoading74 && synCatalog74.isEmpty {
                    Button("Reintentar") { Task { await synLoadCatalog74() } }
                }
            }.font(.caption).foregroundStyle(.secondary)
            if !synCatalogError74.isEmpty {
                Text(synCatalogError74).font(.caption).foregroundStyle(.orange)
            }
            ScrollView {
                LazyVStack(spacing: 3) {
                    ForEach(synDVRPickerResults73) { channel in
                        Button {
                            synDVR55ChannelID = channel.id
                            synDVRPickerOpen73 = false
                        } label: {
                            HStack(spacing: 10) {
                                synChannelPill(channel)
                                Text(synCleanChannelName(channel.name))
                                    .lineLimit(1)
                                Spacer()
                                if synDVR55ChannelID == channel.id {
                                    Image(systemName: "checkmark.circle.fill")
                                }
                            }
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(22)
        .frame(width: 650, height: 560)
        .task { if synCatalog74.isEmpty { await synLoadCatalog74() } }
    }

    // SYN_75_REFINEMENTS: selector Finder; no mueve archivos anteriores ni interrumpe REC.
    private func synChooseDVRFolder75() {
        let chooser = NSOpenPanel()
        chooser.title = "Carpeta de grabaciones SYN"
        chooser.prompt = "Usar esta carpeta"
        chooser.canChooseDirectories = true
        chooser.canChooseFiles = false
        chooser.allowsMultipleSelection = false
        chooser.directoryURL = synDVR53.folder
        chooser.begin { response in
            guard response == .OK, let folder = chooser.url else { return }
            Task { @MainActor in
                do {
                    try SYNRecordingFolder75.save(folder)
                    synDVRFolderPath75 = folder.path
                    synDVR53.refresh()
                    synDVR54Message = "Destino guardado para nuevas grabaciones. Las anteriores se conservan."
                } catch {
                    synDVR54Message = "No se pudo elegir la carpeta: " + error.localizedDescription
                }
            }
        }
    }

    // SYN_DVR_REGRESSION_802: una sola lógica para las dos vistas DVR.
    // "Eliminar" retira el trabajo terminado de la cola, NUNCA el .ts grabado.
    @ViewBuilder
    private func synDVRJobAction802(
        _ job: (id: String, title: String, start: Date, end: Date, state: String)
    ) -> some View {
        if SYNBackgroundDVR54.isRemovable802(job.state) {
            Button("Eliminar", role: .destructive) {
                do {
                    try SYNBackgroundDVR54.remove802(job.id)
                    synDVR54Jobs = SYNBackgroundDVR54.list()
                    if synNotice71.contains(job.title) && synNotice71.contains("ha fallado") {
                        synNotice71 = ""
                    }
                    synDVR54Message = "Entrada eliminada de DVR. El vídeo grabado se conserva."
                } catch {
                    synDVR54Message = "No se pudo eliminar la entrada: " + error.localizedDescription
                }
            }
            .help("Eliminar esta tarea de la lista sin borrar el vídeo")
        } else if SYNBackgroundDVR54.isCancellable802(job.state) {
            Button("Cancelar") {
                SYNBackgroundDVR54.cancel(job.id)
                synDVR54Jobs = SYNBackgroundDVR54.list()
            }
            .help("Solicitar la cancelación de la grabación o programación")
        } else if job.state == "stopping" {
            Text("Deteniendo…").foregroundStyle(.secondary)
        }
    }

    private var synDVRGTK55: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text("DVR · Grabaciones").font(.title2.bold())
                Spacer()
                Button { NSWorkspace.shared.open(synDVR53.folder) } label: {
                    Label("Abrir carpeta", systemImage: "folder")
                }.help("Abrir carpeta de grabaciones en Finder")
                Button { synChooseDVRFolder75() } label: {
                    Label("Elegir carpeta…", systemImage: "folder.badge.gearshape")
                }.help("Elegir dónde guardar las próximas grabaciones")
                Button { synDVR53.refresh(); synDVR54Jobs = SYNBackgroundDVR54.list() } label: {
                    Image(systemName: "arrow.clockwise")
                }.help("Actualizar grabaciones")
            }.padding(.bottom, 15)
            HStack(alignment: .top, spacing: 0) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Programar una grabación").font(.system(size: 17, weight: .semibold))
                    SYN_DVR_CALENDAR_57(selection: $synDVR55Day)
                        .frame(maxWidth: .infinity)
                    Text("Canal").font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
                    Button {
                        synDVRSearch73 = ""
                        synDVRPickerOpen73 = true
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "magnifyingglass")
                            Text(synSelectedDVRChannel74
                                .map { synCleanChannelName($0.name) } ?? "Seleccionar canal…")
                                .lineLimit(1)
                            Spacer()
                            Image(systemName: "chevron.down")
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .buttonStyle(.bordered)
                    .sheet(isPresented: $synDVRPickerOpen73) { synDVRPickerSheet73 }
                    Text("Horario (24 h)").font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary)
                    HStack(spacing: 8) {
                        Text("De")
                        Picker("Hora de inicio", selection: $synDVR55StartHour) {
                            ForEach(0..<24, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                        }.labelsHidden().frame(width: 70)
                        Picker("Minuto de inicio", selection: $synDVR55StartMinute) {
                            ForEach(0..<60, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                        }.labelsHidden().frame(width: 70)
                        Text("a")
                        Picker("Hora de fin", selection: $synDVR55EndHour) {
                            ForEach(0..<24, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                        }.labelsHidden().frame(width: 70)
                        Picker("Minuto de fin", selection: $synDVR55EndMinute) {
                            ForEach(0..<60, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                        }.labelsHidden().frame(width: 70)
                    }.font(.system(size: 13))
                    .controlSize(.large)
                    Button {
                        synDVR55Schedule()
                    } label: {
                        Text("Programar grabación").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(synDVR55ChannelID.isEmpty)
                    Button {
                        guard let selected = synSelectedDVRChannel74,
                              let client = state.client else {
                            synDVR54Message = "Selecciona un canal."; return
                        }
                        do {
                            let url = try client.liveURL(selected)
                            try SYNBackgroundDVR54.add(url: url, channel: selected.name,
                                title: selected.name, start: Date(), end: Date().addingTimeInterval(3600))
                            synDVR54Message = "REC gestionado por SYN DVR Engine 2.0 (1 h)."
                            synDVR54Jobs = SYNBackgroundDVR54.list()
                            sharedRecorderRefresh70 += 1
                        } catch { synDVR54Message = error.localizedDescription }
                    } label: {
                        Label("Grabar canal seleccionado ahora", systemImage: "record.circle.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.pink)
                    .controlSize(.large)
                    .disabled(synDVR55ChannelID.isEmpty)
                    if !synDVR54Message.isEmpty {
                        Text(synDVR54Message).font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Text("Grabación en segundo plano mediante FFmpeg y el servicio de macOS.")
                        .font(.caption2).foregroundStyle(.secondary)
                    Spacer(minLength: 0)
                }
                .frame(width: 455, alignment: .topLeading)
                .padding(.trailing, 22)
                Divider()
                VStack(alignment: .leading, spacing: 9) {
                    Text("Programadas y grabadas").font(.system(size: 17, weight: .semibold))
                    HStack(spacing: 8) {
                        Text("Destino: \(synDVR53.folder.path)")
                            .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        Button("Cambiar…") { synChooseDVRFolder75() }
                            .controlSize(.small)
                    }
                    ScrollView {
                        LazyVStack(spacing: 1) {
                            // SYN_DVR_UI_98: una sola fila por tarea y vídeo finalizado.
                            ForEach(synDVR54Jobs.indices, id: \.self) { index in
                                let job = synDVR54Jobs[index]
                                if !synDVRHiddenJobs98.contains(job.id) {
                                    let recorded = synDVRFileForJob98(job.id)
                                    HStack(spacing: 8) {
                                        Circle().fill(job.state == "recording" ? Color.red : Color.secondary)
                                            .frame(width: 7, height: 7)
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(job.title).font(.system(size: 15, weight: .semibold)).lineLimit(2)
                                            Text("\(job.start.formatted(date: .abbreviated, time: .shortened)) – \(job.end.formatted(date: .omitted, time: .shortened)) · \(job.state)")
                                                .font(.system(size: 12)).foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        if let recorded, synDVRIsFinished98(job.state) {
                                            Button("Ver en SYN") { SYNRecordingWindow93.shared.open(recorded) }
                                                .font(.caption)
                                            Button { NSWorkspace.shared.activateFileViewerSelecting([recorded]) } label: {
                                                Image(systemName: "folder")
                                            }.help("Mostrar en Finder")
                                            Button(role: .destructive) {
                                                synDVRDeleteCandidate98 = recorded
                                                synDVRDeleteConfirmation98 = true
                                            } label: {
                                                Image(systemName: "trash")
                                            }.help("Mover grabación a la Papelera")
                                        } else if synDVRIsFinished98(job.state) {
                                            Button("Quitar de la lista") { synDVRHideJob98(job.id) }
                                                .font(.caption)
                                        } else {
                                            Button("Cancelar") {
                                                SYNBackgroundDVR54.cancel(job.id)
                                                synDVR54Jobs = SYNBackgroundDVR54.list()
                                            }.font(.system(size: 12))
                                        }
                                    }
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 13)
                                    .frame(maxWidth: .infinity, minHeight: 63, alignment: .leading)
                                    .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 6))
                                }
                            }
                            ForEach(synDVR53.files.filter { file in
                                !synDVRHasJobForFile98(file)
                            }, id: \.path) { file in
                                HStack(spacing: 10) {
                                    Image(systemName: "film").foregroundStyle(.secondary)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(file.deletingPathExtension().lastPathComponent)
                                            .font(.system(size: 15, weight: .semibold)).lineLimit(2)
                                        Text("Grabación guardada").font(.system(size: 12)).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Button("Ver en SYN") { SYNRecordingWindow93.shared.open(file) }.font(.caption)
                                    Button { NSWorkspace.shared.activateFileViewerSelecting([file]) } label: {
                                        Image(systemName: "folder")
                                    }.help("Mostrar en Finder")
                                    if ["mkv", "mp4", "mov"].contains(file.pathExtension.lowercased()) {
                                        Button(role: .destructive) {
                                            synDVRDeleteCandidate98 = file
                                            synDVRDeleteConfirmation98 = true
                                        } label: {
                                            Image(systemName: "trash")
                                        }.help("Mover grabación a la Papelera")
                                    }
                                }
                                .padding(.horizontal, 14)
                                .padding(.vertical, 13)
                                .frame(maxWidth: .infinity, minHeight: 63, alignment: .leading)
                                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 6))
                            }
                        }
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .padding(.leading, 18)
            }
            Spacer(minLength: 0)
            HStack(spacing: 6) {
                Circle().fill(Color.green).frame(width: 7, height: 7)
                Text("DVR autónomo disponible en la sesión de macOS; puedes cerrar SYN")
                    .font(.caption2).foregroundStyle(.secondary)
                Spacer()
            }
            .padding(.top, 10)
        }
        .padding(18)
        .confirmationDialog("¿Mover la grabación a la Papelera?", isPresented: $synDVRDeleteConfirmation98) {
            Button("Mover a la Papelera", role: .destructive) { synDVRMoveToTrash98() }
            Button("Cancelar", role: .cancel) { synDVRDeleteCandidate98 = nil }
        } message: {
            Text("La grabación se puede recuperar desde la Papelera. No se modificará ninguna grabación en curso.")
        }
        .onAppear {
            synDVR53.refresh()
            synDVR54Jobs = SYNBackgroundDVR54.list()
            if synDVR55ChannelID.isEmpty { synDVR55ChannelID = state.channels.first?.id ?? "" }
        }
    }

    // SYN_DVR_UI_98: correlación estricta por UUID, NO por título (puede repetirse).
    private func synDVRFileForJob98(_ id: String) -> URL? {
        guard UUID(uuidString: id) != nil else { return nil }
        let suffix = "_" + String(id.prefix(8))
        return synDVR53.files.first { file in
            file.deletingLastPathComponent().lastPathComponent == "SYN-DVR2_" + id ||
            file.deletingPathExtension().lastPathComponent.hasSuffix(suffix)
        }
    }

    private func synDVRIsFinished98(_ state: String) -> Bool {
        ["finished", "completed", "cancelled", "failed", "partial", "expired"].contains(state.lowercased())
    }

    private func synDVRHasJobForFile98(_ file: URL) -> Bool {
        synDVR54Jobs.contains { job in
            synDVRFileForJob98(job.id)?.standardizedFileURL == file.standardizedFileURL &&
            !synDVRHiddenJobs98.contains(job.id)
        }
    }

    private func synDVRHideJob98(_ id: String) {
        guard UUID(uuidString: id) != nil,
              let job = synDVR54Jobs.first(where: { $0.id == id }),
              synDVRIsFinished98(job.state) else { return }
        synDVRHiddenJobs98.insert(id)
        UserDefaults.standard.set(Array(synDVRHiddenJobs98).sorted(), forKey: "syn.native.dvr.hiddenJobs98")
    }

    private func synDVRMoveToTrash98() {
        guard let file = synDVRDeleteCandidate98 else { return }
        synDVRDeleteCandidate98 = nil
        let selected = file.standardizedFileURL
        // No borrar un archivo que la captura esté escribiendo ni un temporal TS.
        guard ["mkv", "mp4", "mov"].contains(selected.pathExtension.lowercased()),
              synDVR53.files.contains(where: { $0.standardizedFileURL == selected }) else {
            synDVR54Message = "Solo se pueden enviar a la Papelera vídeos finalizados de la biblioteca."
            return
        }
        if let job = synDVR54Jobs.first(where: { synDVRFileForJob98($0.id)?.standardizedFileURL == selected }),
           !synDVRIsFinished98(job.state) {
            synDVR54Message = "La grabación sigue activa y no puede eliminarse."
            return
        }
        // El motor mantiene estados reales en otra carpeta distinta de la UI.
        // Si es un MKV de SYN-DVR2, exigir estado final antes de tocarlo.
        let parent = selected.deletingLastPathComponent().lastPathComponent
        if parent.hasPrefix("SYN-DVR2_") {
            let id = String(parent.dropFirst("SYN-DVR2_".count))
            guard UUID(uuidString: id) != nil else {
                synDVR54Message = "Identificador de grabación desconocido; no se elimina."
                return
            }
            let statusURL = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/jobs")
                .appendingPathComponent(id + ".status.json")
            guard let raw = try? Data(contentsOf: statusURL),
                  let status = try? JSONSerialization.jsonObject(with: raw) as? [String: Any],
                  let state = status["state"] as? String,
                  synDVRIsFinished98(state) else {
                synDVR54Message = "El motor no confirma que la grabación haya terminado; no se elimina."
                return
            }
        }
        if synDVR53.isRecording, synDVR53.destination?.standardizedFileURL == selected {
            synDVR54Message = "La grabación continúa activa; no se elimina."
            return
        }
        do {
            try FileManager.default.trashItem(at: selected, resultingItemURL: nil)
            if let job = synDVR54Jobs.first(where: { synDVRFileForJob98($0.id)?.standardizedFileURL == selected }) {
                synDVRHideJob98(job.id)
            }
            if synRecording94.file?.standardizedFileURL == selected { synCloseRecording95() }
            synDVR53.refresh()
            synDVR54Jobs = SYNBackgroundDVR54.list()
            synDVR54Message = "Grabación movida a la Papelera."
        } catch {
            synDVR54Message = "No se pudo mover la grabación a la Papelera: " + error.localizedDescription
        }
    }

    private func synDVR55Schedule() {
        guard let channel = synSelectedDVRChannel74,
              let client = state.client else {
            synDVR54Message = "Selecciona un canal."; return
        }
        var calendar = Calendar.current
        calendar.timeZone = .current
        guard let start = calendar.date(bySettingHour: synDVR55StartHour,
                                      minute: synDVR55StartMinute, second: 0, of: synDVR55Day),
              let end = calendar.date(bySettingHour: synDVR55EndHour,
                                    minute: synDVR55EndMinute, second: 0, of: synDVR55Day),
              end > start, end > Date() else {
            synDVR54Message = "La hora de fin debe ser posterior al inicio y estar en el futuro."
            return
        }
        do {
            try SYNBackgroundDVR54.add(url: client.liveURL(channel), channel: channel.name,
                                       title: channel.name, start: max(Date(), start), end: end)
            synDVR54Message = "Grabación programada correctamente."
            synDVR54Jobs = SYNBackgroundDVR54.list()
        } catch { synDVR54Message = error.localizedDescription }
    }

    // SYN_NATIVE_DVR_53: zona DVR real, sin modificar el reproductor.
    private var synDVRPanel53: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "record.circle").foregroundStyle(.red)
                Text("DVR · Grabaciones").font(.headline)
                Spacer()
                Button { synDVR53.refresh() } label: { Image(systemName: "arrow.clockwise") }
                    .help("Actualizar lista")
                Button { NSWorkspace.shared.open(synDVR53.folder) } label: {
                    Label("Abrir carpeta", systemImage: "folder")
                }
            }
            HStack(spacing: 10) {
                Button {
                    guard let url = state.playingURL else { return }
                    do {
                        let started = try SYNUnifiedDVR2.toggle(url: url, channel: state.playingTitle)
                        synDVR54Message = started ? "REC iniciado en DVR 2.0." : "Detención solicitada a DVR 2.0."
                        synDVR54Jobs = SYNBackgroundDVR54.list()
                    } catch { synDVR54Message = error.localizedDescription }
                } label: {
                    Label("REC canal actual · DVR 2.0", systemImage: "record.circle.fill")
                }
                .disabled(state.playingURL == nil)
                Text("Grabación sin recomprimir; independiente del reproductor").font(.caption).foregroundStyle(.secondary)
            }
            Divider()
            HStack {
                Text("Grabaciones autónomas y programadas").font(.subheadline).bold()
                Spacer()
                Button("Grabar actual 2 h en segundo plano") {
                    guard let url = state.playingURL else { synDVR54Message = "Selecciona un canal."; return }
                    do {
                        try SYNBackgroundDVR54.add(url: url, channel: state.playingTitle,
                            title: state.playingTitle, start: Date(), end: Date().addingTimeInterval(7200))
                        synDVR54Message = "Grabación autónoma creada. Puedes cerrar SYN."
                        synDVR54Jobs = SYNBackgroundDVR54.list()
                    } catch { synDVR54Message = error.localizedDescription }
                }.disabled(state.playingURL == nil)
                Button("Actualizar") { synDVR54Jobs = SYNBackgroundDVR54.list() }
            }
            if !synDVR54Message.isEmpty { Text(synDVR54Message).font(.caption).foregroundStyle(.secondary) }
            ForEach(synDVR54Jobs.indices, id: \.self) { index in
                let job = synDVR54Jobs[index]
                HStack {
                    VStack(alignment: .leading) {
                        Text(job.title).lineLimit(1)
                        Text("\(job.start.formatted(date: .abbreviated, time: .shortened)) – \(job.end.formatted(date: .omitted, time: .shortened)) · \(job.state)")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                    Spacer()
                    synDVRJobAction802(job)
                }
            }
            if !synDVR53.message.isEmpty {
                Text(synDVR53.message).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
            }
            if synDVR53.files.isEmpty {
                ContentUnavailableView("Aún no hay grabaciones", systemImage: "film.stack",
                    description: Text("Sintoniza un canal y pulsa «Grabar canal actual»."))
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(synDVR53.files, id: \.path) { file in
                            HStack {
                                Image(systemName: "film").foregroundStyle(.secondary)
                                Text(file.deletingPathExtension().lastPathComponent).lineLimit(1)
                                Spacer()
                                Button("Ver en SYN") { SYNRecordingWindow93.shared.open(file) }
                                Button { NSWorkspace.shared.activateFileViewerSelecting([file]) } label: {
                                    Image(systemName: "folder")
                                }.help("Mostrar en Finder")
                            }.font(.system(size: 12)).padding(8)
                        }
                    }
                }
            }
        }
        .padding(14)
        .onAppear { synDVR53.refresh(); synDVR54Jobs = SYNBackgroundDVR54.list() }
    }

    private func synSaveXtream7101(_ profile: XtreamProfile, _ typedPassword: String) async throws {
        let editing = profiles.profiles.contains(where: { $0.id == profile.id })
        let password = editing && typedPassword.isEmpty
            ? (CredentialVault.password(id: profile.id) ?? "") : typedPassword
        guard !password.isEmpty else { throw SYNSetupError7101.missingPassword }
        // Primero se autentica: nunca sustituir una conexión válida con datos erróneos.
        _ = try await XtreamClient(profile: profile, password: password).authenticate()
        if editing {
            try profiles.update(profile, password: typedPassword.isEmpty ? nil : typedPassword)
            if state.selectedProfile?.id == profile.id { state.select(profile) }
        } else {
            try profiles.append(profile, password: password)
            lastProfileID = profile.id.uuidString
            synActiveM3UID79 = ""
            state.select(profile)
        }
    }

    private func synSaveM3U7101(_ profile: SYNM3UProfile79) {
        synM3UStore79.save(profile)
        synM3USelect79(profile)
    }
}

// SYN 7.10.1: el alta de perfiles está unificada en SYNProfileSetup7101.swift.

// SYN_NATIVE_EPG_INTERACTIVA_37 — Arrastre horizontal del EPG sin alterar el vídeo.
// SYN_EPG_FIX_40: gesto instalado desde dentro del documento desplazable.
private struct SYNMouseDragScrollBridge: NSViewRepresentable {
    let focusX: CGFloat
    let revision: Int
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeNSView(context: Context) -> NSView { NSView(frame: .zero) }
    func updateNSView(_ view: NSView, context: Context) {
        DispatchQueue.main.async { [weak view] in
            guard let view else { return }
            var ancestor = view.superview
            while let candidate = ancestor {
                if let scroll = candidate as? NSScrollView,
                   let doc = scroll.documentView,
                   doc.bounds.width > scroll.contentSize.width + 50 {
                    context.coordinator.attach(to: scroll)
                    context.coordinator.focus(x: focusX, revision: revision)
                    break
                }
                ancestor = candidate.superview
            }
        }
    }
    final class Coordinator: NSObject, NSGestureRecognizerDelegate {
        weak var scroll: NSScrollView?
        private var gesture: NSPanGestureRecognizer?
        private var lastRevision: Int = -1
        func focus(x: CGFloat, revision: Int) {
            guard revision != lastRevision, let scroll else { return }
            lastRevision = revision
            for delay in [0.05, 0.3] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak scroll] in
                    guard let scroll, let document = scroll.documentView else { return }
                    let clip = scroll.contentView
                    let maxX = max(0, document.bounds.width - clip.bounds.width)
                    let target = min(maxX, max(0, x - clip.bounds.width / 2))
                    clip.scroll(to: NSPoint(x: target, y: clip.bounds.origin.y))
                    scroll.reflectScrolledClipView(clip)
                }
            }
        }
        func attach(to scroll: NSScrollView) {
            guard let document = scroll.documentView else { return }
            if self.scroll === scroll && gesture?.view === document { return }
            if let gesture { gesture.view?.removeGestureRecognizer(gesture) }
            let recognizer = NSPanGestureRecognizer(target: self, action: #selector(drag(_:)))
            recognizer.delegate = self
            document.addGestureRecognizer(recognizer)
            gesture = recognizer
            self.scroll = scroll
        }
        func gestureRecognizer(_ gestureRecognizer: NSGestureRecognizer,
            shouldRecognizeSimultaneouslyWith otherGestureRecognizer: NSGestureRecognizer) -> Bool { true }
        @objc private func drag(_ sender: NSPanGestureRecognizer) {
            guard let scroll, let doc = scroll.documentView else { return }
            let delta = sender.translation(in: doc)
            if abs(delta.x) < 0.1 { return }
            let clip = scroll.contentView
            let maxX = max(0, doc.bounds.width - clip.bounds.width)
            let newX = min(maxX, max(0, clip.bounds.origin.x - delta.x))
            clip.scroll(to: NSPoint(x: newX, y: clip.bounds.origin.y))
            scroll.reflectScrolledClipView(clip)
            sender.setTranslation(.zero, in: doc)
        }
    }
}

// SYN_EPG_NEON_7107 — pigmentos fluorescentes con letra BLANCA en toda la EPG.
// El color base se oscurece solo lo necesario para un contraste minimo 5.3:1
// sobre blanco; la linea de luz superior mantiene la sensacion neón.
private struct SYNEPGGradient7104: ViewModifier {
    let tint: Color
    let enabled: Bool

    private func shaded(_ darkness: CGFloat) -> Color {
        let original = NSColor(tint).usingColorSpace(.deviceRGB) ?? NSColor.systemTeal
        let r = original.redComponent
        let g = original.greenComponent
        let b = original.blueComponent

        func linear(_ v: CGFloat) -> CGFloat {
            let c = min(1, max(0, v))
            return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
        }
        func contrast(_ scale: CGFloat) -> CGFloat {
            let luminance = 0.2126 * linear(r * scale)
                + 0.7152 * linear(g * scale)
                + 0.0722 * linear(b * scale)
            return 1.05 / (luminance + 0.05)
        }
        // Máximo brillo que mantiene el texto blanco legible, también en lima/cian.
        var low: CGFloat = 0
        var high: CGFloat = max(0, min(1, 1 - darkness))
        if contrast(high) >= 5.3 { low = high }
        else {
            for _ in 0..<13 {
                let mid = (low + high) / 2
                if contrast(mid) >= 5.3 { low = mid }
                else { high = mid }
            }
        }
        return Color(red: Double(r * low), green: Double(g * low), blue: Double(b * low))
    }

    func body(content: Content) -> some View {
        content
            .background {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(LinearGradient(
                        stops: [
                            .init(color: shaded(0.10), location: 0),
                            .init(color: shaded(0.23), location: 0.48),
                            .init(color: shaded(0.43), location: 1)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    ))
                    .overlay(alignment: .top) {
                        Capsule()
                            .fill(LinearGradient(
                                colors: [tint.opacity(0.92), tint.opacity(0.10)],
                                startPoint: .leading, endPoint: .trailing
                            ))
                            .frame(height: enabled ? 2 : 1)
                            .padding(.horizontal, 7)
                            .padding(.top, 1)
                            .allowsHitTesting(false)
                    }
            }
            .overlay {
                if enabled {
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .strokeBorder(.white.opacity(0.17), lineWidth: 1)
                        .allowsHitTesting(false)
                }
            }
            .shadow(color: .black.opacity(enabled ? 0.12 : 0), radius: 2, y: 1)
    }
}

// SYN_EPG_POPOVER_797 — AppKit calcula el anclaje en la posición REAL del ratón,
// incluso tras el desplazamiento horizontal de la guía. Evita que la ficha salte
// al origen de la fila o aparezca encima de la columna de canales.
private struct SYNEPGInfoCard: ViewModifier {
    let item: EPGEntry
    let start: Date?
    let end: Date?
    @State private var shown = false
    @State private var hoverTask: Task<Void, Never>?

    func body(content: Content) -> some View {
        content
            .onHover { inside in
                hoverTask?.cancel()
                if inside {
                    hoverTask = Task { @MainActor in
                        try? await Task.sleep(for: .milliseconds(480))
                        guard !Task.isCancelled else { return }
                        shown = true
                    }
                } else {
                    shown = false
                }
            }
            .overlay {
                SYNEPGHoverAnchor797(isPresented: shown, item: item, start: start, end: end)
                    .allowsHitTesting(false)
            }
            .onDisappear { hoverTask?.cancel(); shown = false }
    }
}

private final class SYNEPGNoninteractiveAnchor797: NSView {
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
}

private struct SYNEPGHoverAnchor797: NSViewRepresentable {
    let isPresented: Bool
    let item: EPGEntry
    let start: Date?
    let end: Date?

    final class Coordinator {
        let popover = NSPopover()
        init() {
            popover.behavior = .applicationDefined
            popover.animates = false
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> SYNEPGNoninteractiveAnchor797 {
        SYNEPGNoninteractiveAnchor797(frame: .zero)
    }

    func updateNSView(_ view: SYNEPGNoninteractiveAnchor797, context: Context) {
        let popover = context.coordinator.popover
        guard isPresented else {
            if popover.isShown { popover.close() }
            return
        }
        guard !popover.isShown, let window = view.window,
              let contentView = window.contentView else { return }

        // SYN_EPG_POPOVER_7108 — anclar al puntero REAL, no al origen de la
        // fila virtual (14.550 pt). El borde vertical anterior (.maxY) ponía
        // la burbuja ENCIMA del ratón, sobre filas diferentes en la EPG inferior.
        // Abrimos al LADO del puntero: la flecha permanece a la altura de la
        // pastilla bajo el ratón incluso con scroll vertical y horizontal.
        let screenPoint = NSEvent.mouseLocation
        let windowPoint = window.convertPoint(fromScreen: screenPoint)
        let mouse = contentView.convert(windowPoint, from: nil)
        guard contentView.bounds.contains(mouse) else { return }

        // Seleccionar izquierda/derecha según el espacio real de la pantalla;
        // evita que AppKit desplace la ficha de vuelta hacia la parte superior.
        let visibleFrame = window.screen?.visibleFrame ?? NSScreen.main?.visibleFrame ?? .zero
        let spaceRight = visibleFrame.maxX - screenPoint.x
        let spaceLeft = screenPoint.x - visibleFrame.minX
        let preferredSide: NSRectEdge = (spaceRight >= 380 || spaceRight >= spaceLeft)
            ? .maxX : .minX

        popover.contentViewController = NSHostingController(rootView: SYNEPGPopoverContent797(
            item: item, start: start, end: end
        ))
        popover.show(relativeTo: NSRect(x: mouse.x, y: mouse.y, width: 3, height: 3),
                     of: contentView, preferredEdge: preferredSide)
    }
}

private struct SYNEPGPopoverContent797: View {
    let item: EPGEntry
    let start: Date?
    let end: Date?

    var body: some View {
        ScrollView(.vertical) {
            VStack(alignment: .leading, spacing: 9) {
                Text(item.titleText.isEmpty ? "Programa sin título" : item.titleText)
                    .font(.system(size: 15, weight: .semibold))
                    .fixedSize(horizontal: false, vertical: true)
                if let start {
                    let startText = start.formatted(date: .abbreviated, time: .shortened)
                    let endText = end?.formatted(date: .omitted, time: .shortened)
                    Label(startText + (endText.map { " – " + $0 } ?? ""), systemImage: "clock")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
                if !item.categoryText.isEmpty { metadata("Género", item.categoryText) }
                if !item.ratingText.isEmpty { metadata("Calificación", item.ratingText) }
                if !item.peopleText.isEmpty { metadata("Presentadores / reparto", item.peopleText) }
                if let director = item.director, !director.isEmpty { metadata("Dirección", director) }
                if let country = item.country, !country.isEmpty { metadata("País", country) }
                if let year = item.year, !year.isEmpty { metadata("Año", year) }
                if !item.descriptionText.isEmpty {
                    Divider()
                    Text(item.descriptionText)
                        .font(.system(size: 12))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(15)
            .frame(width: 355, alignment: .leading)
        }
        .frame(width: 355, height: min(330, preferredHeight797))
    }
    private var preferredHeight797: CGFloat {
        let text = item.descriptionText.count + item.peopleText.count + item.titleText.count
        return CGFloat(max(108, min(330, 94 + text / 2)))
    }
    private func metadata(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label + ":").foregroundStyle(.secondary).frame(width: 120, alignment: .leading)
            Text(value).fixedSize(horizontal: false, vertical: true)
        }
        .font(.system(size: 11))
    }
}


// SYN_CHANNEL_ART_43 — pastilla con paleta real o lettering vectorial
// SYN_PLACEHOLDER_FLAT_POP_972: solo cuando no existe logo del canal.
struct SYNChannelArtworkPill: View {
    let name: String
    let source: String
    var fallbackSource: String = ""
    @StateObject private var imageStore = SYNChannelImageStore()

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8)
                .fill(imageStore.image.map(SYNChannelImageStore.pillColor) ?? placeholderColor)

            if let img = imageStore.image {
                // Los logos reales (incluidos los personalizados) se muestran como antes.
                if imageStore.hasOwnBackground {
                    Image(nsImage: imageStore.ownBackgroundCrop ?? img)
                        .resizable()
                        .interpolation(.high)
                        .scaledToFill()
                        .contrast(1.12)
                        .brightness(0.085)
                        .frame(width: 106, height: 43)
                        .clipped()
                } else {
                    Image(nsImage: img)
                        .resizable()
                        .scaledToFit()
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                }
            } else {
                GeometryReader { geo in
                    ZStack {
                        // Flat: solo rellenos planos, sin blanco, sin sombras y sin degradados.
                        RoundedRectangle(cornerRadius: 8)
                            .fill(placeholderPalette[0])

                        popShapes(popVariant, width: geo.size.width,
                                  height: geo.size.height, colors: placeholderPalette)

                        Text(cleanName)
                            .font(.system(size: nameFontSize, weight: .black, design: .rounded))
                            .tracking(cleanName.count > 19 ? -0.35 : 0.10)
                            .foregroundStyle(Self.popColor(0x172138))
                            .lineLimit(2)
                            .minimumScaleFactor(0.64)
                            .allowsTightening(true)
                            .multilineTextAlignment(.center)
                            .frame(width: max(40, geo.size.width - 13),
                                   height: max(20, geo.size.height - 3))
                    }
                    .frame(width: geo.size.width, height: geo.size.height)
                    .clipped()
                }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .onAppear { imageStore.load(source, fallback: fallbackSource) }
        .onChange(of: source) { _, next in imageStore.load(next, fallback: fallbackSource) }
        .onChange(of: fallbackSource) { _, next in imageStore.load(source, fallback: next) }
    }

    private var cleanName: String { synCleanChannelName(name).uppercased() }

    private var nameFontSize: CGFloat {
        if cleanName.count > 26 { return 8.0 }
        if cleanName.count > 17 { return 9.0 }
        if cleanName.count > 11 { return 10.2 }
        return 11.8
    }

    private var hash64: UInt64 {
        cleanName.utf8.reduce(UInt64(1469598103934665603)) {
            ($0 ^ UInt64($1)) &* 1099511628211
        }
    }

    // Variante geométrica independiente de la paleta. Permanece estable para cada canal.
    private var popVariant: Int { Int((hash64 >> 21) % 12) }

    private static func popColor(_ hex: UInt32) -> Color {
        Color(red: Double((hex >> 16) & 255) / 255,
              green: Double((hex >> 8) & 255) / 255,
              blue: Double(hex & 255) / 255)
    }

    // 20 paletas luminosas, saturadas y sin blanco; 12 formas = 240 combinaciones.
    // En todas, el texto azul-negro tiene contraste suficiente con el fondo y los acentos.
    private var placeholderPalette: [Color] {
        let palettes: [[UInt32]] = [
            [0xFFE344, 0xFF67B7, 0x49EAD1, 0xB693FF],
            [0xBFFF4E, 0xFE8953, 0x5DCEFF, 0xF98EC7],
            [0x54EEDA, 0xFF7373, 0xE78CFF, 0xF3CC38],
            [0x6EDEFF, 0xFFAA33, 0xFF6AA7, 0x91F445],
            [0xFFB351, 0x4ACFD8, 0xB693FF, 0xC6F35C],
            [0xFF8FC7, 0x5DCEFF, 0x91F445, 0xF3CC38],
            [0xC1AAFF, 0xFE8953, 0x49EAD1, 0xFFAA33],
            [0xFFAA8B, 0x7AEC7E, 0x5DCEFF, 0xE78CFF],
            [0x90E887, 0xFF67B7, 0xF3A457, 0x8AB5FF],
            [0xFFCF66, 0x4ACFD8, 0xFF6AA7, 0xB693FF],
            [0x7ADBF2, 0xFF7373, 0xC6F35C, 0xF98EC7],
            [0xF9A2DB, 0x49EAD1, 0xFFAA33, 0x8AB5FF],
            [0x9FE7AC, 0xE78CFF, 0xFF7373, 0x5DCEFF],
            [0xE4BCFF, 0xF3CC38, 0x49EAD1, 0xFE8953],
            [0xE5F05A, 0xFF6AA7, 0xB693FF, 0x4ACFD8],
            [0x9CC5FF, 0xFE8953, 0x91F445, 0xF98EC7],
            [0xFFB16F, 0x49EAD1, 0xE78CFF, 0xC6F35C],
            [0xE6B0FB, 0x4ACFD8, 0xFFAA33, 0x7AEC7E],
            [0x7AEFD5, 0xFF67B7, 0xF3CC38, 0x8AB5FF],
            [0xFFD47C, 0xE78CFF, 0x5DCEFF, 0x91F445]
        ]
        return palettes[Int(hash64 % UInt64(palettes.count))].map(Self.popColor)
    }

    private var placeholderColor: Color { placeholderPalette[0] }

    // 12 composiciones asimétricas: geometría en los bordes, nombre despejado.
    @ViewBuilder private func popShapes(_ variant: Int, width w: CGFloat,
                                        height h: CGFloat, colors c: [Color]) -> some View {
        switch variant {
        case 0: // dos discos
            Circle().fill(c[1]).frame(width: 43, height: 43).offset(x: -w * 0.43, y: -h * 0.19)
            Circle().fill(c[2]).frame(width: 25, height: 25).offset(x: w * 0.43, y: h * 0.22)
        case 1: // diagonales recortadas
            Rectangle().fill(c[1]).frame(width: 17, height: 92).rotationEffect(.degrees(-27)).offset(x: -w * 0.41)
            Rectangle().fill(c[2]).frame(width: 11, height: 92).rotationEffect(.degrees(27)).offset(x: w * 0.43)
        case 2: // cuadrícula pop
            ForEach(0..<3, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2).fill(i == 1 ? c[2] : c[1])
                    .frame(width: 16, height: 11).offset(x: -w * 0.43, y: CGFloat(i - 1) * 15)
            }
            Circle().fill(c[3]).frame(width: 32, height: 32).offset(x: w * 0.46, y: h * 0.20)
        case 3: // anillos cortados
            Circle().stroke(c[1], lineWidth: 7).frame(width: 54, height: 54).offset(x: -w * 0.48, y: h * 0.05)
            Circle().fill(c[2]).frame(width: 21, height: 21).offset(x: w * 0.44, y: -h * 0.19)
        case 4: // barras verticales y punto
            RoundedRectangle(cornerRadius: 3).fill(c[1]).frame(width: 9, height: 48).offset(x: -w * 0.48, y: 2)
            RoundedRectangle(cornerRadius: 3).fill(c[2]).frame(width: 8, height: 38).offset(x: -w * 0.35, y: -7)
            Circle().fill(c[3]).frame(width: 26, height: 26).offset(x: w * 0.44, y: h * 0.26)
        case 5: // confeti geométrico
            Circle().fill(c[1]).frame(width: 17, height: 17).offset(x: -w * 0.42, y: -h * 0.24)
            Rectangle().fill(c[2]).frame(width: 13, height: 13).rotationEffect(.degrees(28)).offset(x: w * 0.44, y: -h * 0.17)
            Capsule().fill(c[3]).frame(width: 27, height: 9).rotationEffect(.degrees(-32)).offset(x: -w * 0.40, y: h * 0.30)
        case 6: // semicircunferencias
            Circle().fill(c[1]).frame(width: 62, height: 62).offset(x: -w * 0.52, y: 0)
            Circle().fill(c[2]).frame(width: 43, height: 43).offset(x: -w * 0.61, y: 0)
            Circle().fill(c[3]).frame(width: 42, height: 42).offset(x: w * 0.52, y: -h * 0.04)
        case 7: // damero asimétrico
            ForEach(0..<2, id: \.self) { row in
                ForEach(0..<2, id: \.self) { col in
                    Rectangle().fill((row + col) % 2 == 0 ? c[1] : c[2])
                        .frame(width: 15, height: 14)
                        .offset(x: -w * 0.44 + CGFloat(col) * 15, y: -h * 0.33 + CGFloat(row) * 14)
                }
            }
            Circle().fill(c[3]).frame(width: 28, height: 28).offset(x: w * 0.45, y: h * 0.22)
        case 8: // doble chevrón
            Rectangle().fill(c[1]).frame(width: 13, height: 55).rotationEffect(.degrees(-36)).offset(x: -w * 0.44, y: -h * 0.19)
            Rectangle().fill(c[2]).frame(width: 13, height: 55).rotationEffect(.degrees(36)).offset(x: -w * 0.44, y: h * 0.20)
            Capsule().fill(c[3]).frame(width: 10, height: 40).offset(x: w * 0.46, y: 0)
        case 9: // sol pop recortado
            Circle().fill(c[1]).frame(width: 43, height: 43).offset(x: w * 0.47, y: -h * 0.18)
            Circle().stroke(c[2], lineWidth: 4).frame(width: 61, height: 61).offset(x: w * 0.47, y: -h * 0.18)
            RoundedRectangle(cornerRadius: 4).fill(c[3]).frame(width: 22, height: 28).offset(x: -w * 0.46, y: h * 0.26)
        case 10: // cápsulas y puntos
            Capsule().fill(c[1]).frame(width: 42, height: 14).rotationEffect(.degrees(49)).offset(x: -w * 0.47, y: h * 0.04)
            Circle().fill(c[2]).frame(width: 10, height: 10).offset(x: w * 0.37, y: -h * 0.28)
            Circle().fill(c[3]).frame(width: 16, height: 16).offset(x: w * 0.48, y: h * 0.21)
        default: // marcos de color y bloques
            RoundedRectangle(cornerRadius: 5).stroke(c[1], lineWidth: 7)
                .frame(width: 39, height: 46).rotationEffect(.degrees(21)).offset(x: -w * 0.47, y: 0)
            Rectangle().fill(c[2]).frame(width: 24, height: 18).rotationEffect(.degrees(-18)).offset(x: w * 0.47, y: -h * 0.22)
            Capsule().fill(c[3]).frame(width: 31, height: 7).offset(x: w * 0.42, y: h * 0.34)
        }
    }
}

private final class SYNChannelImageStore: ObservableObject {
    @Published var image: NSImage?
    @Published private(set) var hasOwnBackground = false
    @Published private(set) var ownBackgroundCrop: NSImage?
    private var current = ""
    private var task: URLSessionDataTask?
    private static var cache: [String: NSImage] = [:]
    // Las URL de logos del proveedor se fuerzan a red sin vaciar URLCache global.
    private static var providerInvalidated96: Set<String> = []

    static func invalidateProviderImages96(_ sources: [String]) -> Int {
        let urls = Set(sources.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { value in
            guard let url = URL(string: value), let scheme = url.scheme?.lowercased() else { return false }
            return scheme == "http" || scheme == "https"
        })
        for value in urls {
            cache.removeValue(forKey: value) // Solo el objeto descargado del proveedor.
            providerInvalidated96.insert(value)
            if let url = URL(string: value) {
                URLCache.shared.removeCachedResponse(for: URLRequest(url: url))
            }
        }
        return urls.count
    }

    private var requestedFallback = ""

    func load(_ path: String, fallback: String = "") {
        let token = path + "\u{0}" + fallback
        guard token != current else { return }
        current = token
        requestedFallback = fallback
        task?.cancel()
        image = nil
        hasOwnBackground = false
        ownBackgroundCrop = nil
        fetch(path, token: token, allowFallback: true)
    }

    private func fetch(_ path: String, token: String, allowFallback: Bool) {
        let clean = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else {
            if allowFallback { useOriginal(token: token, previous: clean) }
            return
        }
        if let cached = Self.cache[clean] { setImage622(cached); return }
        if let url = URL(string: clean), ["https", "http"].contains(url.scheme?.lowercased() ?? "") {
            let forceRemote96 = Self.providerInvalidated96.contains(clean)
            var request = URLRequest(url: url,
                                     cachePolicy: forceRemote96 ? .reloadIgnoringLocalCacheData : .returnCacheDataElseLoad,
                                     timeoutInterval: 16)
            if forceRemote96 { request.setValue("no-cache", forHTTPHeaderField: "Cache-Control") }
            // Varios proveedores Xtream/CDN rechazan el User-Agent por defecto de URLSession.
            request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", forHTTPHeaderField: "User-Agent")
            request.setValue("image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5", forHTTPHeaderField: "Accept")
            task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
                let validHTTP = (response as? HTTPURLResponse).map { (200..<300).contains($0.statusCode) } ?? false
                let decoded = (error == nil && validHTTP && (data?.count ?? 0) < 8_000_000)
                    ? data.flatMap { NSImage(data: $0) } : nil
                DispatchQueue.main.async {
                    guard let self, self.current == token else { return }
                    if let decoded {
                        Self.cache[clean] = decoded
                        Self.providerInvalidated96.remove(clean)
                        self.setImage622(decoded)
                    } else if allowFallback {
                        self.useOriginal(token: token, previous: clean)
                    }
                }
            }
            task?.resume()
        } else if let img = NSImage(contentsOfFile: clean) {
            Self.cache[clean] = img
            setImage622(img)
        } else if allowFallback {
            useOriginal(token: token, previous: clean)
        }
    }

    private func useOriginal(token: String, previous: String) {
        let original = requestedFallback.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !original.isEmpty, original != previous else { return }
        fetch(original, token: token, allowFallback: false)
    }

    // SYN_622_OWN_BG_FULLBLEED — detection happens only on image load.
    // Fully opaque, approximately uniform edges => pre-coloured channel artwork.
    // Translucent PNG logos, photographs and multicolour edges keep current mode.
    private func setImage622(_ original: NSImage) {
        let result = Self.detectOwnBackground622(original)
        ownBackgroundCrop = result
        hasOwnBackground = result != nil
        image = original
    }

    private static func detectOwnBackground622(_ original: NSImage) -> NSImage? {
        guard let tiff = original.tiffRepresentation,
              let bmp = NSBitmapImageRep(data: tiff),
              bmp.pixelsWide >= 36, bmp.pixelsHigh >= 24 else { return nil }
        let w = bmp.pixelsWide, h = bmp.pixelsHigh

        func rgb(_ x: Int, _ y: Int) -> (CGFloat, CGFloat, CGFloat, CGFloat)? {
            guard let c = bmp.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { return nil }
            return (c.redComponent, c.greenComponent, c.blueComponent, c.alphaComponent)
        }
        // Sample only the outer 2% of the actual image, not a synthetic palette.
        let px = max(1, w / 50), py = max(1, h / 50)
        var edge: [(CGFloat, CGFloat, CGFloat, CGFloat)] = []
        for i in 0..<12 {
            let x = px + (w - 2 * px - 1) * i / 11
            if let p = rgb(x, py) { edge.append(p) }
            if let p = rgb(x, h - py - 1) { edge.append(p) }
        }
        for i in 0..<8 {
            let y = py + (h - 2 * py - 1) * i / 7
            if let p = rgb(px, y) { edge.append(p) }
            if let p = rgb(w - px - 1, y) { edge.append(p) }
        }
        guard edge.count >= 30 else { return nil }
        // Locate a representative colour among actual border samples.
        func distance(_ a: (CGFloat, CGFloat, CGFloat, CGFloat),
                      _ b: (CGFloat, CGFloat, CGFloat, CGFloat)) -> CGFloat {
            max(abs(a.0 - b.0), max(abs(a.1 - b.1), abs(a.2 - b.2)))
        }
        guard let background = edge.max(by: { candidateA, candidateB in
            edge.filter { distance($0, candidateA) <= 0.085 && $0.3 >= 0.94 }.count <
            edge.filter { distance($0, candidateB) <= 0.085 && $0.3 >= 0.94 }.count
        }) else { return nil }
        guard background.3 >= 0.94,
              edge.filter({ distance($0, background) <= 0.085 && $0.3 >= 0.94 }).count * 100 >= edge.count * 82 else {
            return nil
        }

        // Pick the best vertical crop around the foreground so 16:9 logos
        // can fill a 106:43 pill without becoming miniature.
        let wantedH = min(h, max(1, Int((CGFloat(w) * 43.0 / 106.0).rounded())))
        guard wantedH < h else { return original }
        var first = h, last = 0
        for y in stride(from: py, to: h - py, by: max(1, h / 96)) {
            for x in stride(from: px, to: w - px, by: max(1, w / 128)) {
                guard let p = rgb(x, y), p.3 > 0.6 else { continue }
                if distance(p, background) > 0.18 {
                    first = min(first, y)
                    last = max(last, y)
                }
            }
        }
        let middle = first <= last ? (first + last) / 2 : h / 2
        let originY = max(0, min(h - wantedH, middle - wantedH / 2))
        guard let cgImage = bmp.cgImage?.cropping(
            to: CGRect(x: 0, y: CGFloat(originY), width: CGFloat(w), height: CGFloat(wantedH))
        ) else { return original }
        return NSImage(cgImage: cgImage, size: NSSize(width: CGFloat(w), height: CGFloat(wantedH)))
    }

    // SYN_ALPHA46_PALETTE: gris azulado solo para logos sin color.
    // SYN_ALPHA47_EDITORIAL: preserva matiz, selecciona contraste por luminancia.
    // Negro => gris azulado claro; blanco => color intenso oscuro; rojo/naranja => vivos.
    // SYN_ALPHA49_COLOR_FIEL: conservar color y corregir contraste solo cuando haga falta.
    static func pillColor(_ image: NSImage) -> Color {
        guard let tiff = image.tiffRepresentation,
              let bmp = NSBitmapImageRep(data: tiff),
              bmp.pixelsWide > 0, bmp.pixelsHigh > 0 else {
            return Color(red: 0.72, green: 0.82, blue: 0.88)
        }
        var sx = 0.0, sy = 0.0, chroma = 0.0, total = 0.0
        var luma = 0.0
        var samples: [(Double, Double)] = []
        let dx = max(1, bmp.pixelsWide / 32), dy = max(1, bmp.pixelsHigh / 24)
        for y in stride(from: 0, to: bmp.pixelsHigh, by: dy) {
            for x in stride(from: 0, to: bmp.pixelsWide, by: dx) {
                guard let c = bmp.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB),
                      c.alphaComponent > 0.30 else { continue }
                var h: CGFloat = 0, sat: CGFloat = 0, bright: CGFloat = 0, alpha: CGFloat = 0
                c.getHue(&h, saturation: &sat, brightness: &bright, alpha: &alpha)
                let weight = Double(alpha)
                let r = Double(c.redComponent), g = Double(c.greenComponent), b = Double(c.blueComponent)
                let luminance = 0.2126*r + 0.7152*g + 0.0722*b
                luma += luminance * weight; total += weight
                samples.append((luminance, weight))
                if sat > 0.22 && bright > 0.16 {
                    let strength = Double(sat * alpha)
                    sx += cos(Double(h) * 2 * .pi) * strength
                    sy += sin(Double(h) * 2 * .pi) * strength
                    chroma += strength
                }
            }
        }
        guard total > 0 else { return Color(red: 0.72, green: 0.82, blue: 0.88) }
        let avg = luma / total
        let hasColor = chroma / total > 0.035
        if !hasColor {
            // Únicamente logos verdaderamente neutros van a la familia gris azulada.
            return avg < 0.53
                ? Color(red: 0.73, green: 0.83, blue: 0.90)
                : Color(red: 0.42, green: 0.56, blue: 0.67) // SYN_LOGO_BRIGHT_796
        }
        let hue = (atan2(sy, sx) / (2 * Double.pi) + 1).truncatingRemainder(dividingBy: 1)
        let warm = hue < 0.13 || hue > 0.96
        // Paleta saturada: el contraste se ajusta con la LUMINOSIDAD,
        // nunca volviendo gris todo el fondo.
        // SYN_LOGO_PASTEL_797: los fondos generados quedan inequívocamente más
        // claros y menos saturados; el contraste del logo decide el tono.
        let satCandidates: [Double] = warm ? [0.23, 0.31, 0.42] : [0.20, 0.29, 0.40]
        let brightCandidates: [Double] = [0.87, 0.92, 0.96, 1.0]
        func contrast(_ a: Double, _ b: Double) -> Double {
            (max(a,b) + 0.05) / (min(a,b) + 0.05)
        }
        var winner = (s: 0.28, b: 0.94)
        var top = -Double.infinity
        for sat in satCandidates {
            for brightness in brightCandidates {
                guard let ns = NSColor(calibratedHue: CGFloat(hue), saturation: CGFloat(sat),
                                       brightness: CGFloat(brightness), alpha: 1)
                                        .usingColorSpace(.deviceRGB) else { continue }
                let bg = 0.2126*Double(ns.redComponent)
                    + 0.7152*Double(ns.greenComponent)
                    + 0.0722*Double(ns.blueComponent)
                // Contraste robusto: usar la media de peor cuartil, pero evitar
                // sacrificar el color corporativo para ganar unas décimas.
                let values = samples.map { contrast($0.0,bg) }.sorted()
                let n = max(1, values.count / 4)
                let low = values.prefix(n).reduce(0,+) / Double(n)
                let score = min(low, 4.0) - sat * 0.16
                    + brightness * 0.18
                if score > top { top = score; winner = (sat, brightness) }
            }
        }
        return Color(hue: hue, saturation: winner.s, brightness: winner.b)
    }
}


// SYN_ALPHA50_CLEAN_NAME: visual-only. IDs, raw names, search and URLs unchanged.
private func synCleanChannelName(_ source: String) -> String {
    var result = source.trimmingCharacters(in: .whitespacesAndNewlines)
    let expression = #"^\s*(?:(?:\|\s*)?(?:ES|ESP|SPAIN|LAT|LATAM|US|USA|UK|GB|MX|AR|CL|CO|PE|PT|FR|DE|IT|BR)(?:\s*\|\s*|\s*[:\-–]\s*))+"#
    result = result.replacingOccurrences(of: expression, with: "", options: [.regularExpression, .caseInsensitive])
    result = result.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
    return result.trimmingCharacters(in: .whitespacesAndNewlines)
}

// SYN_APPLE_APPEARANCE_52 — colores neutros Apple, sin modificar colores EPG ni logos.
private struct SYNApplePalette52 {
    let dark: Bool
    let accent: Color
    var background: Color { dark ? Color(red: 0.085, green: 0.091, blue: 0.105) : Color(red: 0.974, green: 0.978, blue: 0.986) }
    var sidebar: Color { dark ? Color(red: 0.12, green: 0.125, blue: 0.145) : Color(red: 0.936, green: 0.944, blue: 0.960) }
    var panel: Color { dark ? Color(red: 0.15, green: 0.155, blue: 0.175) : Color(red: 0.960, green: 0.965, blue: 0.976) }
    var surface: Color { dark ? Color(red: 0.22, green: 0.23, blue: 0.25) : Color.white }
    var foreground: Color { dark ? Color(red: 0.96, green: 0.96, blue: 0.98) : Color(red: 0.15, green: 0.16, blue: 0.19) }
    var muted: Color { dark ? Color(red: 0.68, green: 0.70, blue: 0.73) : Color(red: 0.42, green: 0.45, blue: 0.50) }
    static func parseHex(_ text: String) -> Color {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "#", with: "")
        guard value.count == 6, let number = UInt32(value, radix: 16) else { return Color(nsColor: .controlAccentColor) }
        return Color(red: Double((number >> 16) & 255)/255, green: Double((number >> 8) & 255)/255, blue: Double(number & 255)/255)
    }
    static func hex(_ color: Color) -> String? {
        guard let c = NSColor(color).usingColorSpace(.deviceRGB) else { return nil }
        return String(format: "#%02X%02X%02X", Int((c.redComponent * 255).rounded()), Int((c.greenComponent * 255).rounded()), Int((c.blueComponent * 255).rounded()))
    }
}

// SYN_75_REFINEMENTS — Carpeta de grabaciones configurable y compartida con launchd.
// La configuración afecta a nuevas grabaciones; las activas mantienen su archivo.
enum SYNRecordingFolder75 {
    static let preference = "syn.native.dvrFolderPath.v1"
    static var current: URL {
        if let chosen = UserDefaults.standard.string(forKey: preference),
           chosen.hasPrefix("/") && !chosen.isEmpty {
            return URL(fileURLWithPath: chosen, isDirectory: true)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Movies/SYN Grabaciones", isDirectory: true)
    }
    static func save(_ folder: URL) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        guard fm.isWritableFile(atPath: folder.path) else {
            throw NSError(domain: "SYN DVR", code: 75,
                userInfo: [NSLocalizedDescriptionKey: "La carpeta seleccionada no permite escribir."])
        }
        let root = fm.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN Native DVR", isDirectory: true)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        let data = try JSONSerialization.data(withJSONObject: ["folder": folder.path])
        let config = root.appendingPathComponent("recording_folder.json")
        try data.write(to: config, options: .atomic)
        try fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: config.path)
        UserDefaults.standard.set(folder.path, forKey: preference)
    }
}

// SYN_NATIVE_DVR_53 — Grabación del directo mediante FFmpeg, independiente de VLC.
@MainActor
private final class SYNDVRRecorder53: ObservableObject {
    @Published private(set) var isRecording = false
    @Published private(set) var channel = ""
    @Published private(set) var files: [URL] = []
    @Published var message = ""

    private var process: Process?
    private var input: Pipe?
    private(set) var destination: URL?
    private var stopping = false

    var folder: URL { SYNRecordingFolder75.current }

    func refresh() {
        let manager = FileManager.default
        // SYN_RECORDING_IN_WINDOW_94: la versión 3.1 guarda MKV en SYN-DVR2_UUID.
        // Mostrar los terminados sin moverlos a la raíz; ignorar piezas part_*.ts.
        // No se modifica ningún vídeo, directorio ni archivo de estado.
        var roots: [URL] = [folder]
        let remote = manager.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Remote/server.json")
        if let data = try? Data(contentsOf: remote),
           let config = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let chosen = config["recordingsFolder"] as? String, chosen.hasPrefix("/") {
            let extra = URL(fileURLWithPath: chosen, isDirectory: true).standardizedFileURL
            if !roots.contains(extra) { roots.append(extra) }
        }
        var found: [URL: URL] = [:]
        let allowed: Set<String> = ["mkv", "mp4", "mov", "ts"]
        for root in roots where manager.fileExists(atPath: root.path) {
            // Conservar archivos directos, más una carpeta de grabación por tarea.
            let children = (try? manager.contentsOfDirectory(at: root,
                includingPropertiesForKeys: [.isDirectoryKey, .contentModificationDateKey],
                options: [.skipsHiddenFiles])) ?? []
            for item in children {
                let directory = (try? item.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
                let candidates: [URL] = directory && item.lastPathComponent.hasPrefix("SYN-DVR2_")
                    ? ((try? manager.contentsOfDirectory(at: item,
                       includingPropertiesForKeys: [.contentModificationDateKey],
                       options: [.skipsHiddenFiles])) ?? [])
                    : (directory ? [] : [item])
                for candidate in candidates {
                    guard allowed.contains(candidate.pathExtension.lowercased()),
                          !candidate.lastPathComponent.hasPrefix("part_") else { continue }
                    found[candidate.standardizedFileURL] = candidate
                }
            }
        }
        files = found.values.sorted { a, b in
            let aa = (try? a.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let bb = (try? b.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return aa > bb
        }
    }

    func record(url: URL?, title: String) {
        guard !isRecording else { message = "Ya se está grabando \(channel)."; return }
        guard let url, ["http", "https"].contains(url.scheme?.lowercased() ?? "") else {
            message = "Selecciona primero un canal en directo."; return
        }
        guard let executable = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
            .first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
            message = "No encuentro FFmpeg. Instálalo con: brew install ffmpeg"; return
        }
        do { try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true) }
        catch { message = "No puedo crear la carpeta de grabaciones: \(error.localizedDescription)"; return }

        let safe = String(title.replacingOccurrences(of: #"[^\p{L}\p{N} ._-]"#, with: "_", options: .regularExpression).prefix(72))
        let stamp = DateFormatter()
        stamp.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        let target = folder.appendingPathComponent("\(safe.isEmpty ? "Directo" : safe)_\(stamp.string(from: Date())).ts")
        let task = Process()
        task.executableURL = URL(fileURLWithPath: executable)
        task.arguments = ["-hide_banner", "-loglevel", "error", "-nostats", "-rw_timeout", "15000000",
                          "-user_agent", SYNPlaybackUserAgent911.current, "-i", url.absoluteString,
                          "-map", "0:v?", "-map", "0:a?", "-c", "copy", "-f", "mpegts", target.path]
        let pipe = Pipe()
        task.standardInput = pipe
        task.standardOutput = FileHandle.nullDevice
        // No guardar stderr: FFmpeg puede imprimir la URL Xtream con credenciales.
        task.standardError = FileHandle.nullDevice
        task.terminationHandler = { [weak self] finished in
            let code = finished.terminationStatus
            Task { @MainActor [weak self] in
                guard let self, self.process === finished else { return }
                let manuallyStopped = self.stopping
                self.isRecording = false
                self.process = nil
                self.input = nil
                self.stopping = false
                self.refresh()
                self.message = manuallyStopped ? "Grabación finalizada." :
                    (code == 0 ? "Grabación finalizada." : "FFmpeg se ha detenido (código \(code)). Comprueba la emisión.")
            }
        }
        do {
            try task.run()
            process = task
            input = pipe
            stopping = false
            destination = target
            channel = title
            isRecording = true
            message = "Grabando \(title) en \(folder.lastPathComponent)."
            refresh()
        } catch {
            message = "No se ha podido iniciar FFmpeg: \(error.localizedDescription)"
        }
    }

    func stop() {
        guard isRecording, let task = process else { return }
        stopping = true
        if let bytes = "q\n".data(using: .utf8) {
            try? input?.fileHandleForWriting.write(contentsOf: bytes)
        }
        // FFmpeg procesa q y cierra correctamente el archivo TS.
        message = "Finalizando grabación…"
        if !task.isRunning { refresh() }
    }
}

// SYN_DVR_BACKGROUND_54 — portable private job queue for the launchd worker.
private struct SYNBackgroundDVR54 {
    static var directory: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0/jobs", isDirectory: true)
    }
    // SYN_NAMES_92 — nombres de tareas de grabación, sin alterar las URL ni los tiempos.
    // YY/DD/MM significa año/día/mes, literalmente como se ha solicitado.
    private static func recordingName92(channel: String, title: String,
                                        start: Date, isEPG: Bool) -> String {
        let cleanChannel = channel.replacingOccurrences(of: #"[\r\n\t]"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanTitle = title.replacingOccurrences(of: #"[\r\n\t]"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let date = DateFormatter()
        date.locale = Locale(identifier: "es_ES_POSIX")
        date.timeZone = .current
        date.dateFormat = "yy/dd/MM"
        let day = date.string(from: start)
        let channelName = cleanChannel.isEmpty ? "Canal" : cleanChannel
        if isEPG {
            let program = cleanTitle.isEmpty ? "Programa" : cleanTitle
            return "\(program) - \(channelName) - \(day)"
        }
        date.dateFormat = "HH:mm"
        return "\(channelName) - \(day) - \(date.string(from: start))"
    }

    static func add(url: URL, channel: String, title: String, start: Date, end: Date,
                    epg: Bool? = nil, eventDate: Date? = nil) throws {
        guard end > Date(), end > start, ["http", "https"].contains(url.scheme?.lowercased() ?? "") else {
            throw NSError(domain: "SYN DVR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Horario o URL inválido"])
        }
        guard SYNUnifiedDVR2.workerOnline else {
            throw NSError(domain: "SYN DVR", code: 2000, userInfo: [NSLocalizedDescriptionKey:
                "El motor SYN DVR 2.0 no está activo. Revisa el servicio antes de grabar."])
        }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let id = UUID().uuidString
        let cleanTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanChannel = channel.trimmingCharacters(in: .whitespacesAndNewlines)
        let inferredEPG = !cleanTitle.isEmpty &&
            cleanTitle.localizedCaseInsensitiveCompare(cleanChannel) != .orderedSame
        let label = recordingName92(channel: channel, title: title,
                                    start: eventDate ?? start, isEPG: epg ?? inferredEPG)
        let data = try JSONSerialization.data(withJSONObject: [
            "url": url.absoluteString, "channel": channel, "title": label,
            "start": start.timeIntervalSince1970, "end": end.timeIntervalSince1970,
            "folder": SYNRecordingFolder75.current.path,
            "namingVersion": 2
        ])
        let staging = directory.appendingPathComponent(id + ".pending")
        let final = directory.appendingPathComponent(id + ".json")
        guard FileManager.default.createFile(atPath: staging.path, contents: data,
            attributes: [.posixPermissions: NSNumber(value: 0o600)]) else {
            throw NSError(domain: "SYN DVR", code: 2, userInfo: [NSLocalizedDescriptionKey: "No se pudo guardar la tarea"])
        }
        try FileManager.default.moveItem(at: staging, to: final)
    }
    static func list() -> [(id: String, title: String, start: Date, end: Date, state: String)] {
        let files = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        return files.filter { $0.pathExtension == "json" && !$0.lastPathComponent.hasSuffix(".status.json") }.compactMap { url in
            guard let data = try? Data(contentsOf: url),
                let job = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let title = job["title"] as? String, let start = job["start"] as? Double,
                let end = job["end"] as? Double else { return nil }
            let statusURL = directory.appendingPathComponent(url.deletingPathExtension().lastPathComponent + ".status.json")
            let statusData = (try? Data(contentsOf: statusURL)) ?? Data()
            let record = (try? JSONSerialization.jsonObject(with: statusData)) as? [String: Any]
            return (id: url.deletingPathExtension().lastPathComponent, title: title,
                start: Date(timeIntervalSince1970: start), end: Date(timeIntervalSince1970: end),
                state: record?["state"] as? String ?? "programada")
        }.sorted { $0.start < $1.start }
    }
    // SYN_DVR_REGRESSION_802: cancelar solo tareas aún ejecutables;
    // el worker recibe la orden mediante .cancel, sin detener su servicio.
    static func isCancellable802(_ state: String) -> Bool {
        ["scheduled", "programada", "recording", "retrying", "reconnecting"].contains(state)
    }
    static func isRemovable802(_ state: String) -> Bool {
        ["failed", "cancelled", "expired", "partial"].contains(state)
    }
    static func remove802(_ id: String) throws {
        guard UUID(uuidString: id) != nil else {
            throw NSError(domain: "SYN DVR", code: 802,
                          userInfo: [NSLocalizedDescriptionKey: "Identificador no válido"])
        }
        let fm = FileManager.default
        let jobURL = directory.appendingPathComponent(id + ".json")
        let statusURL = directory.appendingPathComponent(id + ".status.json")
        guard fm.fileExists(atPath: jobURL.path),
              let data = try? Data(contentsOf: statusURL),
              let record = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let state = record["state"] as? String,
              isRemovable802(state) else {
            throw NSError(domain: "SYN DVR", code: 803,
                          userInfo: [NSLocalizedDescriptionKey:
                                     "Solo se pueden eliminar tareas fallidas, canceladas o caducadas"])
        }
        // Eliminar primero el trabajo impide que el worker vuelva a descubrirlo.
        // Ni el archivo de vídeo ni el directorio de grabaciones se modifican.
        for url in [jobURL, statusURL, directory.appendingPathComponent(id + ".cancel")] {
            if fm.fileExists(atPath: url.path) { try fm.removeItem(at: url) }
        }
    }
    static func cancel(_ id: String) {
        guard UUID(uuidString: id) != nil else { return }
        let path = directory.appendingPathComponent(id + ".cancel")
        FileManager.default.createFile(atPath: path.path, contents: Data(), attributes: [.posixPermissions: NSNumber(value: 0o600)])
    }
    static func removeUnified(_ id: String) {
        guard UUID(uuidString: id) != nil else { return }
        let fm = FileManager.default
        let statusPath = directory.appendingPathComponent(id + ".status.json")
        guard let data = try? Data(contentsOf: statusPath),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let state = object["state"] as? String,
              ["failed", "cancelled", "expired", "partial"].contains(state) else { return }
        for suffix in [".json", ".status.json", ".cancel"] {
            try? fm.removeItem(at: directory.appendingPathComponent(id + suffix))
        }
    }
}


// SYN_EPG_MARGINS_90: horarios de emisión EPG + margen opcional, sin alterar el motor.
struct SYNEPGMarginRequest90: Identifiable {
    let id = UUID()
    let url: URL
    let channel: String
    let title: String
    let start: Date
    let end: Date
}

struct SYNEPGMarginChooser90: View {
    let title: String
    let epgStart: Date
    let epgEnd: Date
    let onSchedule: (Date, Date) throws -> Void
    let onClose: () -> Void

    @State private var before: Int
    @State private var after: Int
    @State private var errorMessage = ""

    init(title: String, epgStart: Date, epgEnd: Date,
         onSchedule: @escaping (Date, Date) throws -> Void,
         onClose: @escaping () -> Void) {
        self.title = title
        self.epgStart = epgStart
        self.epgEnd = epgEnd
        self.onSchedule = onSchedule
        self.onClose = onClose
        let prefs = UserDefaults.standard
        _before = State(initialValue: max(0, min(120,
            (prefs.object(forKey: "syn.native.epgMarginBefore90") as? Int) ?? 5)))
        _after = State(initialValue: max(0, min(180,
            (prefs.object(forKey: "syn.native.epgMarginAfter90") as? Int) ?? 10)))
    }

    private var actualStart: Date {
        max(Date(), epgStart.addingTimeInterval(Double(-before) * 60))
    }
    private var actualEnd: Date {
        epgEnd.addingTimeInterval(Double(after) * 60)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("Programar grabación", systemImage: "record.circle.fill")
                    .font(.title3.bold())
                Spacer()
                Button { onClose() } label: { Image(systemName: "xmark.circle.fill") }
                    .buttonStyle(.plain)
            }
            Text(title).font(.headline).lineLimit(2)
            Text("Horario anunciado: " +
                epgStart.formatted(date: .abbreviated, time: .shortened) + " – " +
                epgEnd.formatted(date: .omitted, time: .shortened))
                .font(.caption).foregroundStyle(.secondary)
            Divider()
            Stepper(value: $before, in: 0...120, step: 1) {
                HStack {
                    Text("Empezar antes")
                    Spacer()
                    Text("\(before) min").monospacedDigit().bold()
                }
            }
            Stepper(value: $after, in: 0...180, step: 1) {
                HStack {
                    Text("Terminar después")
                    Spacer()
                    Text("\(after) min").monospacedDigit().bold()
                }
            }
            VStack(alignment: .leading, spacing: 5) {
                Text("La grabación se programará de:")
                    .font(.caption).foregroundStyle(.secondary)
                Text(actualStart.formatted(date: .abbreviated, time: .shortened) +
                     " → " + actualEnd.formatted(date: .abbreviated, time: .shortened))
                    .font(.system(.body, design: .rounded).weight(.semibold))
                if epgStart.addingTimeInterval(Double(-before) * 60) < Date() {
                    Text("El inicio previsto ya ha pasado: comenzará ahora.")
                        .font(.caption).foregroundStyle(.orange)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color.secondary.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
            if !errorMessage.isEmpty {
                Text(errorMessage).foregroundStyle(.red).font(.caption)
            }
            HStack {
                Button("Cancelar", action: onClose)
                Spacer()
                Button("Programar") {
                    guard actualEnd > actualStart else {
                        errorMessage = "El programa ya ha terminado."; return
                    }
                    do {
                        try onSchedule(actualStart, actualEnd)
                        UserDefaults.standard.set(before, forKey: "syn.native.epgMarginBefore90")
                        UserDefaults.standard.set(after, forKey: "syn.native.epgMarginAfter90")
                        onClose()
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(actualEnd <= actualStart)
            }
        }
        .padding(22)
        .frame(width: 455)
    }
}

// SYN_DVR_CALENDAR_57 — calendario de tamaño real, sin DatePicker gráfico compacto.
private struct SYN_DVR_CALENDAR_57: View {
    @Binding var selection: Date
    @State private var visibleMonth = Calendar.current.startOfMonthSYN57(for: Date())
    private let weekdays = ["L", "M", "X", "J", "V", "S", "D"]
    private var cal: Calendar { var c = Calendar.current; c.firstWeekday = 2; return c }
    private var monthDays: [Date?] {
        guard let interval = cal.dateInterval(of: .month, for: visibleMonth),
              let range = cal.range(of: .day, in: .month, for: visibleMonth) else { return [] }
        let dayOne = interval.start
        let offset = (cal.component(.weekday, from: dayOne) + 5) % 7
        return Array(repeating: nil, count: offset) + range.compactMap { cal.date(byAdding: .day, value: $0-1, to: dayOne) }.map(Optional.some)
    }
    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Text(visibleMonth.formatted(.dateTime.month(.wide).year()))
                    .font(.system(size: 17, weight: .semibold))
                Spacer()
                Button { changeMonth(-1) } label: { Image(systemName: "chevron.left") }
                Button { visibleMonth = cal.startOfMonthSYN57(for: Date()) } label: { Text("Hoy") }
                Button { changeMonth(1) } label: { Image(systemName: "chevron.right") }
            }.buttonStyle(.borderless)
            .font(.system(size: 13))
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: 7), spacing: 5) {
                ForEach(0..<7, id: \.self) { i in
                    Text(weekdays[i]).font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 24)
                }
                ForEach(Array(monthDays.enumerated()), id: \.offset) { _, day in
                    if let day {
                        Button {
                            selection = day
                        } label: {
                            Text("\(cal.component(.day, from: day))")
                                .font(.system(size: 15, weight: cal.isDate(day, inSameDayAs: selection) ? .bold : .regular))
                                .frame(maxWidth: .infinity, minHeight: 39)
                                .foregroundStyle(cal.isDate(day, inSameDayAs: selection) ? Color.white : Color.primary)
                                .background(cal.isDate(day, inSameDayAs: selection) ? Color.accentColor : Color.clear,
                                            in: RoundedRectangle(cornerRadius: 8))
                                .overlay {
                                    if cal.isDateInToday(day) && !cal.isDate(day, inSameDayAs: selection) {
                                        RoundedRectangle(cornerRadius: 8).stroke(Color.accentColor.opacity(0.65), lineWidth: 1)
                                    }
                                }
                        }.buttonStyle(.plain)
                    } else {
                        Color.clear.frame(height: 39)
                    }
                }
            }
        }
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
        .onAppear { visibleMonth = cal.startOfMonthSYN57(for: selection) }
        .onChange(of: selection) { _, next in
            if !cal.isDate(next, equalTo: visibleMonth, toGranularity: .month) {
                visibleMonth = cal.startOfMonthSYN57(for: next)
            }
        }
    }
    private func changeMonth(_ delta: Int) {
        if let changed = cal.date(byAdding: .month, value: delta, to: visibleMonth) { visibleMonth = changed }
    }
}
private extension Calendar {
    func startOfMonthSYN57(for date: Date) -> Date {
        dateInterval(of: .month, for: date)?.start ?? startOfDay(for: date)
    }
}

// EPGEntry only contains immutable Sendable primitives and FlexibleID.
extension EPGEntry: Sendable {}


// SYN_SCROLL_OVERLAY_795
// Overlay scrollers (translucent, auto-fading) without changing system-wide
// AppleShowScrollBars or interfering with Mission Control / other apps.
private struct SYNScrollerOverlay795: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { SYNScrollerProbe795(frame: .zero) }
    func updateNSView(_ view: NSView, context: Context) {
        (view as? SYNScrollerProbe795)?.apply795()
    }
}

private final class SYNScrollerProbe795: NSView {
    private var observer795: Timer?
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        observer795?.invalidate()
        observer795 = nil
        guard window != nil else { return }
        DispatchQueue.main.async { [weak self] in self?.apply795() }
        observer795 = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.apply795()
        }
    }
    func apply795() {
        guard let root = window?.contentView else { return }
        func visit(_ view: NSView) {
            if let scroll = view as? NSScrollView {
                if scroll.scrollerStyle != .overlay { scroll.scrollerStyle = .overlay }
                scroll.verticalScroller?.alphaValue = 0.68
                scroll.horizontalScroller?.alphaValue = 0.68
            }
            for child in view.subviews { visit(child) }
        }
        visit(root)
    }
    deinit { observer795?.invalidate() }
}

// SYN_RESPONSIVE_SPLIT_7106 — ningún recorte de filas: alturas discretas por
// fila completa, mientras el reproductor 16:9 aprovecha el área restante.
private struct SYNResponsiveSplit7106 {
    static let rowHeight: CGFloat = 56
    static let rowSpacing: CGFloat = 2
    static let headerHeight: CGFloat = 34
    static let footerHeight: CGFloat = 14
    // Cabecera + eje horario (28) + separaciones (12) + pie (14)
    // + margen interior scroll (4) + exterior EPG (24).
    static let chromeHeight: CGFloat = 116
    static let rowStep: CGFloat = rowHeight + rowSpacing

    let rows: Int
    let guideHeight: CGFloat
    let playerHeight: CGFloat

    init(size: CGSize, expanded: Bool) {
        let available = max(0, size.height)
        let maxVideoHeight = max(0, (size.width - 6) * 9 / 16)
        let baseRows = 4
        let targetShare: CGFloat = expanded ? 0.52 : 0.41
        let suggestedRows = Int(floor((available * targetShare - Self.chromeHeight) / Self.rowStep))
        // Si la anchura impide seguir aumentando el vídeo sin deformar el 16:9,
        // dedicar la altura sobrante a MÁS filas completas de EPG.
        let spareRows = Int(floor((available - maxVideoHeight - Self.chromeHeight) / Self.rowStep))
        // Dejar un mínimo útil de vídeo cuando se amplía mucho la ventana.
        let videoFloor: CGFloat = 220
        let maxRowsWithVideo = Int(floor((available - videoFloor - Self.chromeHeight) / Self.rowStep))
        let rowCount = max(baseRows, min(max(baseRows, suggestedRows, spareRows), max(baseRows, maxRowsWithVideo)))
        rows = rowCount
        guideHeight = Self.chromeHeight + CGFloat(rowCount) * Self.rowStep
        playerHeight = max(90, min(maxVideoHeight, available - guideHeight))
    }
}

// SYN_UNIFIED_DVR_2_0 — Bridge único REC/EPG/programador/menú.
// No altera el HLS de VLC y nunca ejecuta FFmpeg dentro de la interfaz.
enum SYNUnifiedDVR2 {
    static let root = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
    static var directory: URL { root.appendingPathComponent("jobs", isDirectory: true) }
    static var workerOnline: Bool {
        let path = root.appendingPathComponent("worker.heartbeat.json")
        guard let data = try? Data(contentsOf: path),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let stamp = object["timestamp"] as? Double else { return false }
        let age = Date().timeIntervalSince1970 - stamp
        return age >= -5 && age < 12
    }
    static func activeJob(for url: URL) -> String? {
        let fm = FileManager.default
        let now = Date().timeIntervalSince1970
        let entries = (try? fm.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        for path in entries where path.pathExtension == "json" && UUID(uuidString: path.deletingPathExtension().lastPathComponent) != nil {
            guard let data = try? Data(contentsOf: path),
                  let job = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let source = job["url"] as? String, source == url.absoluteString,
                  let start = job["start"] as? Double, let end = job["end"] as? Double,
                  start < now + 3, end > now else { continue }
            let id = path.deletingPathExtension().lastPathComponent
            let statusURL = directory.appendingPathComponent(id + ".status.json")
            let statusData = (try? Data(contentsOf: statusURL)) ?? Data()
            let status = (try? JSONSerialization.jsonObject(with: statusData)) as? [String: Any]
            let state = status?["state"] as? String ?? "scheduled"
            if ["scheduled", "programada", "recording", "retrying", "reconnecting", "stopping"].contains(state) {
                return id
            }
        }
        return nil
    }
    static func isRecording(url: URL?) -> Bool {
        guard let url else { return false }
        return activeJob(for: url) != nil
    }
    @discardableResult
    static func toggle(url: URL, channel: String) throws -> Bool {
        if let id = activeJob(for: url) {
            SYNBackgroundDVR54.cancel(id)
            return false
        }
        try SYNBackgroundDVR54.add(url: url, channel: channel, title: channel,
            start: Date(), end: Date().addingTimeInterval(7200))
        return true
    }
}

// SYN_REMOTE_PAIRING_40 — SYN client: IP + port + optional password ONLY.
// TOFU: remember first successfully authenticated server certificate in Keychain;
// refuse subsequent certificate changes (including when password is optional).
private final class SYNRemotePin40: NSObject, URLSessionDelegate {
    private let expected: String?
    private(set) var observed: String?
    private(set) var mismatch = false

    init(expected: String?) {
        self.expected=expected?.uppercased()
    }
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let trust=challenge.protectionSpace.serverTrust,
              let cert=SecTrustGetCertificateAtIndex(trust,0) else {
            completionHandler(.cancelAuthenticationChallenge,nil);return
        }
        let data=SecCertificateCopyData(cert) as Data
        let actual=SHA256.hash(data:data).map { String(format:"%02X",$0) }.joined()
        if let expected, expected != actual {
            mismatch=true
            completionHandler(.cancelAuthenticationChallenge,nil);return
        }
        observed=actual
        completionHandler(.useCredential,URLCredential(trust:trust))
    }
}

@MainActor
private struct SYNRemotePairing40: View {
    @AppStorage("syn.remote.dvr.host") private var host="127.0.0.1"
    @AppStorage("syn.remote.dvr.port") private var port="8090"
    @State private var password=""
    @State private var result="Servidor todavía no comprobado"
    @State private var testing=false
    private var target: String { host.trimmingCharacters(in:.whitespacesAndNewlines) + ":" + port }

    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            Text("Conectar con SYN DVR").font(.headline)
            HStack {
                TextField("Dirección IP",text:$host).textFieldStyle(.roundedBorder)
                TextField("Puerto",text:$port).textFieldStyle(.roundedBorder).frame(width:90)
            }
            SecureField("Contraseña (opcional)",text:$password).textFieldStyle(.roundedBorder)
            HStack {
                Button(testing ? "Conectando…" : "Conectar") { test() }.disabled(testing)
                Spacer()
                Label("Conexión HTTPS",systemImage:"lock.shield")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text(result).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
        }
        .onAppear { password=readSecret(service:"SYN DVR Password") ?? "" }
        .onChange(of:host) { _ in password=readSecret(service:"SYN DVR Password") ?? "" }
        .onChange(of:port) { _ in password=readSecret(service:"SYN DVR Password") ?? "" }
    }

    private func readSecret(service:String) -> String? {
        let query:[String:Any]=[
            kSecClass as String:kSecClassGenericPassword,
            kSecAttrService as String:service,
            kSecAttrAccount as String:target,
            kSecReturnData as String:true,
            kSecMatchLimit as String:kSecMatchLimitOne]
        var value:CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary,&value)==errSecSuccess,
              let data=value as? Data else { return nil }
        return String(data:data,encoding:.utf8)
    }
    @discardableResult
    private func saveSecret(_ value:String?,service:String) -> Bool {
        let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,
                                 kSecAttrService as String:service,
                                 kSecAttrAccount as String:target]
        SecItemDelete(query as CFDictionary)
        guard let value,let data=value.data(using:.utf8), !value.isEmpty else {return true}
        var add=query
        add[kSecValueData as String]=data
        add[kSecAttrAccessible as String]=kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(add as CFDictionary,nil)==errSecSuccess
    }
    private func test() {
        let ip=host.trimmingCharacters(in:.whitespacesAndNewlines)
        guard let n=Int(port), (1024...65535).contains(n),
              !ip.isEmpty,!ip.contains("/"),!ip.contains("@"),!ip.contains(" ") else {
            result="Comprueba la dirección IP y el puerto (1024–65535).";return
        }
        var components=URLComponents()
        components.scheme="https";components.host=ip;components.port=n
        components.path="/api/v1/status"
        guard let url=components.url else {result="Dirección IP o puerto no válidos.";return}
        testing=true
        let pin=SYNRemotePin40(expected:readSecret(service:"SYN DVR TLS Pin"))
        let session=URLSession(configuration:.ephemeral,delegate:pin,delegateQueue:nil)
        var req=URLRequest(url:url);req.timeoutInterval=8
        if !password.isEmpty {
            req.setValue(Data(password.utf8).base64EncodedString(),forHTTPHeaderField:"X-SYN-DVR-Password-B64")
        }
        Task {
            defer {session.invalidateAndCancel();testing=false}
            do {
                let (data,response)=try await session.data(for:req)
                guard let http=response as? HTTPURLResponse else { result="Respuesta inválida.";return }
                if http.statusCode==401 {result="El servidor requiere otra contraseña.";return}
                guard http.statusCode==200 else { result="Error del servidor: \(http.statusCode)";return }
                guard let status=try JSONSerialization.jsonObject(with:data) as? [String:Any],
                      status["product"] as? String == "SYN DVR" else {
                    result="El servicio respondió, pero no es un servidor SYN DVR.";return
                }
                guard let observed=pin.observed else {result="No se pudo verificar el certificado HTTPS.";return}
                if !saveSecret(observed,service:"SYN DVR TLS Pin") ||
                   !saveSecret(password,service:"SYN DVR Password") {
                    result="Conectado, pero el Llavero no pudo guardar los datos.";return
                }
                let engine=status["engine"] as? [String:Any] ?? [:]
                result="Conectado a SYN DVR · Motor \((engine["running"] as? Bool ?? false) ? "activo" : "sin respuesta")"
            } catch {
                result=pin.mismatch
                    ? "El certificado del servidor ha cambiado. Conexión bloqueada para protegerte."
                    : "No se pudo conectar. Comprueba IP, puerto y estado de SYN DVR."
            }
        }
    }
}
