import SwiftUI
import AppKit
import UniformTypeIdentifiers

// SYN 7.10.1: Una sola ventana para elegir fuente, escribir credenciales y guardar.
// Los secretos Xtream no aparecen precargados: el Llavero conserva la clave al editar.
enum SYNSetupError7101: LocalizedError {
    case missingPassword, invalidURL
    var errorDescription: String? {
        switch self {
        case .missingPassword: "Es necesario introducir una contraseña para conectar."
        case .invalidURL: "Introduce una URL HTTP/HTTPS válida o selecciona un archivo M3U."
        }
    }
}

struct SYNProfileSetup7101: View {
    private enum Page { case choose, xtream, m3u }
    let existing: XtreamProfile?
    let onXtream: (XtreamProfile, String) async throws -> Void
    let onM3U: (SYNM3UProfile79) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var page: Page
    @State private var profileName: String
    @State private var server: String
    @State private var username: String
    @State private var password = ""
    @State private var output: XtreamProfile.StreamOutput
    @State private var m3uName = "Mi lista"
    @State private var m3uURL = ""
    @State private var xmlURL = ""
    @State private var m3uFile: URL?
    @State private var xmlFile: URL?
    @State private var busy = false
    @State private var failure: String?

    init(existing: XtreamProfile?,
         onXtream: @escaping (XtreamProfile, String) async throws -> Void,
         onM3U: @escaping (SYNM3UProfile79) -> Void) {
        self.existing = existing
        self.onXtream = onXtream
        self.onM3U = onM3U
        _page = State(initialValue: existing == nil ? .choose : .xtream)
        _profileName = State(initialValue: existing?.name ?? "Mi televisión")
        _server = State(initialValue: existing?.server ?? "")
        _username = State(initialValue: existing?.username ?? "")
        _output = State(initialValue: existing?.output ?? .m3u8)
    }

    private let teal = Color(red: 0.13, green: 0.72, blue: 0.74)
    private let orange = Color(red: 1.0, green: 0.49, blue: 0.17)

    var body: some View {
        HStack(spacing: 0) {
            editorial
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    if page != .choose && existing == nil {
                        Button { page = .choose } label: {
                            Label("Volver", systemImage: "chevron.left")
                        }.buttonStyle(.plain).foregroundStyle(.secondary)
                    } else {
                        Text(existing == nil ? "NUEVA FUENTE" : "EDITAR CONEXIÓN")
                            .font(.system(size: 11, weight: .semibold)).tracking(1.3)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .semibold))
                            .frame(width: 30, height: 30)
                            .background(.quaternary, in: Circle())
                    }.buttonStyle(.plain).help("Cerrar")
                }.padding(.bottom, 19)

                switch page {
                case .choose: choicePage
                case .xtream: xtreamPage
                case .m3u: m3uPage
                }
                Spacer(minLength: 0)
            }
            .padding(30)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Color(nsColor: .windowBackgroundColor))
        }
        .frame(width: 850, height: 588)
        .background(Color(nsColor: .windowBackgroundColor))
        .alert("No se pudo guardar la fuente", isPresented: Binding(
            get: { failure != nil }, set: { if !$0 { failure = nil } })) {
                Button("Entendido", role: .cancel) { failure = nil }
            } message: { Text(failure ?? "Error desconocido") }
    }

    private var editorial: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "tv")
                    .font(.system(size: 19))
                    .frame(width: 40, height: 40)
                    .background(.white.opacity(0.13), in: RoundedRectangle(cornerRadius: 13))
                Text("SYN").font(.system(size: 23, weight: .bold, design: .rounded))
            }
            Spacer()
            Text("TODO LO QUE\nQUIERES VER.")
                .font(.system(size: 28, weight: .bold, design: .rounded))
                .tracking(-0.6)
                .fixedSize(horizontal: false, vertical: true)
            Text("Tus canales y su programación. En un lugar hecho para disfrutar de la televisión.")
                .font(.system(size: 13))
                .foregroundStyle(.white.opacity(0.77))
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 14)
            Spacer()
            HStack(spacing: 3) {
                ForEach(0..<7, id: \.self) { index in
                    Rectangle().fill([
                        Color(red:0.70,green:0.96,blue:0.40),
                        Color(red:0.39,green:0.85,blue:0.80),
                        Color(red:0.32,green:0.67,blue:0.97),
                        Color(red:0.57,green:0.48,blue:0.92),
                        Color(red:0.95,green:0.43,blue:0.65),
                        Color(red:1.0,green:0.57,blue:0.39),
                        Color(red:1.0,green:0.82,blue:0.37)
                    ][index]).frame(height: 9)
                }
            }.clipShape(RoundedRectangle(cornerRadius: 4))
            Text(existing == nil ? "ELIGE · CONECTA · DISFRUTA" : "TU CONEXIÓN, A TU GUSTO")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundStyle(.white.opacity(0.62))
                .padding(.top, 13)
        }
        .padding(27)
        .frame(width: 272)
        .frame(maxHeight: .infinity, alignment: .leading)
        .foregroundStyle(.white)
        .background(LinearGradient(colors: [Color(red:0.13,green:0.31,blue:0.36), Color(red:0.06,green:0.13,blue:0.19)], startPoint: .topLeading, endPoint: .bottomTrailing))
    }

    private var choicePage: some View {
        VStack(alignment: .leading, spacing: 13) {
            Text("Tu televisión empieza aquí")
                .font(.system(size: 25, weight: .semibold))
            Text("Añade un proveedor o una lista. La configuración se completa aquí mismo, sin abrir más ventanas.")
                .font(.system(size: 13)).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, 13)
            sourceChoice("Xtream Codes", subtitle: "Servidor, usuario y contraseña", icon: "network", color: orange) { page = .xtream }
            sourceChoice("Lista M3U / M3U8", subtitle: "Enlace o archivo, con guía XMLTV opcional", icon: "list.bullet.rectangle", color: teal) { page = .m3u }
            Spacer(minLength: 20)
            Label("Tus contraseñas Xtream se guardan en el Llavero de macOS.", systemImage: "lock.shield")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func sourceChoice(_ title: String, subtitle: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 15) {
                Image(systemName: icon).font(.system(size: 22)).foregroundStyle(color)
                    .frame(width: 56, height: 56)
                    .background(color.opacity(0.12), in: RoundedRectangle(cornerRadius: 15))
                VStack(alignment: .leading, spacing: 5) {
                    Text(title).font(.system(size: 17, weight: .semibold)).foregroundStyle(.primary)
                    Text(subtitle).font(.system(size: 12)).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "arrow.right").font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(color)
            }
            .padding(15)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 17))
            .overlay(RoundedRectangle(cornerRadius: 17).stroke(color.opacity(0.25), lineWidth: 1))
        }.buttonStyle(.plain)
    }

    private func inputTitle(_ title: String) -> some View {
        Text(title.uppercased()).font(.system(size: 10, weight: .semibold)).tracking(0.6)
            .foregroundStyle(.secondary)
    }

    private var xtreamPage: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text(existing == nil ? "Conectar con Xtream" : "Editar proveedor")
                .font(.system(size: 25, weight: .semibold))
            Text(existing == nil ? "Introduce los datos de tu proveedor." : "Modifica lo que necesites. Si dejas la contraseña vacía, conservaremos la actual.")
                .font(.system(size: 12)).foregroundStyle(.secondary)
                .padding(.bottom, 4)
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 5) {
                    inputTitle("Nombre que verás en SYN")
                    TextField("Mi televisión", text: $profileName).textFieldStyle(.roundedBorder)
                }
                VStack(alignment: .leading, spacing: 5) {
                    inputTitle("Servidor")
                    TextField("http://servidor:puerto", text: $server).textFieldStyle(.roundedBorder)
                }
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 5) {
                        inputTitle("Usuario")
                        TextField("Usuario", text: $username).textFieldStyle(.roundedBorder)
                    }
                    VStack(alignment: .leading, spacing: 5) {
                        inputTitle("Contraseña")
                        SecureField(existing == nil ? "Contraseña" : "Sin cambios", text: $password)
                            .textFieldStyle(.roundedBorder)
                    }
                }
                HStack {
                    Text("Formato de reproducción").font(.system(size: 12))
                    Spacer()
                    Picker("Formato", selection: $output) {
                        Text("HLS · m3u8").tag(XtreamProfile.StreamOutput.m3u8)
                        Text("MPEG-TS · ts").tag(XtreamProfile.StreamOutput.ts)
                    }.labelsHidden().frame(width: 170)
                }
            }
            .padding(18)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 16))
            Label("Contraseñas protegidas en el Llavero. Las conexiones HTTP no están cifradas.", systemImage: "lock.shield")
                .font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 2)
            HStack {
                Button("Cancelar") { dismiss() }
                Spacer()
                Button(busy ? "Verificando…" : (existing == nil ? "Conectar y guardar" : "Guardar cambios")) { saveXtream() }
                    .buttonStyle(.borderedProminent).tint(orange)
                    .disabled(busy || !xtreamValid)
            }
        }
    }

    private var xtreamValid: Bool {
        !profileName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !server.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        (existing != nil || !password.isEmpty)
    }
    private func saveXtream() {
        guard xtreamValid else { return }
        let profile = XtreamProfile(id: existing?.id ?? UUID(),
                                    name: profileName.trimmingCharacters(in: .whitespacesAndNewlines),
                                    server: server.trimmingCharacters(in: .whitespacesAndNewlines),
                                    username: username.trimmingCharacters(in: .whitespacesAndNewlines), output: output)
        busy = true
        Task { @MainActor in
            defer { busy = false }
            do {
                try await onXtream(profile, password)
                dismiss()
            } catch { failure = error.localizedDescription }
        }
    }

    private var m3uPage: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Añadir lista M3U").font(.system(size: 25, weight: .semibold))
            Text("Pega la dirección de tu lista o selecciona un archivo. XMLTV es opcional.")
                .font(.system(size: 12)).foregroundStyle(.secondary)
                .padding(.bottom, 4)
            VStack(alignment: .leading, spacing: 15) {
                VStack(alignment: .leading, spacing: 5) {
                    inputTitle("Nombre de la lista")
                    TextField("Mi lista", text: $m3uName).textFieldStyle(.roundedBorder)
                }
                VStack(alignment: .leading, spacing: 5) {
                    inputTitle("URL de la lista")
                    TextField("https://servidor/lista.m3u", text: $m3uURL).textFieldStyle(.roundedBorder)
                    HStack {
                        Text(m3uFile?.lastPathComponent ?? "O selecciona un archivo M3U/M3U8")
                            .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        Spacer()
                        Button("Elegir archivo…") { m3uFile = chooseFile(["m3u", "m3u8", "txt"]) }
                    }
                }
                Divider()
                VStack(alignment: .leading, spacing: 5) {
                    inputTitle("Guía XMLTV · Opcional")
                    TextField("https://servidor/guia.xml", text: $xmlURL).textFieldStyle(.roundedBorder)
                    HStack {
                        Text(xmlFile?.lastPathComponent ?? "Puedes usar un archivo XML o GZ")
                            .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        Spacer()
                        Button("Elegir XMLTV…") { xmlFile = chooseFile(["xml", "gz"]) }
                    }
                }
            }
            .padding(18)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 16))
            Spacer(minLength: 4)
            HStack {
                Button("Cancelar") { dismiss() }
                Spacer()
                Button("Guardar lista") { saveM3U() }
                    .buttonStyle(.borderedProminent).tint(teal)
                    .disabled(m3uName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                              (m3uURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && m3uFile == nil))
            }
        }
    }

    private func saveM3U() {
        do {
            let id = UUID()
            let playlist = try m3uFile.map { try SYNM3UStore79.retainLocalFile($0, for: id, ext: "m3u") }
                ?? m3uURL.trimmingCharacters(in: .whitespacesAndNewlines)
            let xml = try xmlFile.map { try SYNM3UStore79.retainLocalFile($0, for: id, ext: "xmltv") }
                ?? xmlURL.trimmingCharacters(in: .whitespacesAndNewlines)
            if m3uFile == nil, !["http", "https"].contains(URL(string: playlist)?.scheme?.lowercased() ?? "") {
                throw SYNSetupError7101.invalidURL
            }
            let profile = SYNM3UProfile79(id: id, name: m3uName.trimmingCharacters(in: .whitespacesAndNewlines),
                                         playlist: playlist, guide: xml)
            onM3U(profile)
            dismiss()
        } catch { failure = error.localizedDescription }
    }

    private func chooseFile(_ types: [String]) -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = types.compactMap { UTType(filenameExtension: $0) }
        return panel.runModal() == .OK ? panel.url : nil
    }
}
