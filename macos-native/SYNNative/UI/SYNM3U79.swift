import Foundation
import SwiftUI
import AppKit
import UniformTypeIdentifiers

// SYN Native 7.9 — M3U/M3U8 and external XMLTV. Never stores Xtream passwords.
struct SYNM3UProfile79: Codable, Identifiable, Hashable {
    var id: UUID
    var name: String
    var playlist: String // URL or copied local file URL
    var guide: String    // XMLTV URL or copied local file URL, optional
}

struct SYNM3UChannel79: Identifiable, Hashable {
    let id: String
    let name: String
    let stream: URL
    let group: String
    let logo: String?
    let tvgID: String
}

struct SYNM3UProgramme79: Identifiable, Hashable {
    let id: String
    let title: String
    let start: Date
    let end: Date
    let detail: String
}

private enum SYNM3UError79: LocalizedError {
    case invalidURL, badFile, emptyPlaylist, oversize, xmlInvalid, badHTTP(Int)
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Dirección de lista o guía no válida."
        case .badFile: return "No se pudo leer el archivo seleccionado."
        case .emptyPlaylist: return "La lista no contiene canales reproducibles."
        case .oversize: return "La fuente supera el tamaño máximo permitido."
        case .xmlInvalid: return "La guía XMLTV no es válida o está incompleta."
        case .badHTTP(let code): return "El servidor respondió HTTP \(code)."
        }
    }
}

@MainActor final class SYNM3UStore79: ObservableObject {
    @Published private(set) var profiles: [SYNM3UProfile79] = []
    @Published private(set) var channels: [SYNM3UChannel79] = []
    @Published private(set) var programmes: [String: [SYNM3UProgramme79]] = [:]
    @Published var loading = false
    @Published var notice: String? = nil
    @Published var category = ""
    @Published var search = ""
    @Published var favoritesOnly = false
    @Published private(set) var favorites = Set<String>()
    private let profilesKey = "syn.native.m3uProfiles79"
    private let favoritesKey = "syn.native.m3uFavorites79"
    private var loadRevision = UUID()
    init() {
        if let data = UserDefaults.standard.data(forKey: profilesKey),
           let decoded = try? JSONDecoder().decode([SYNM3UProfile79].self, from: data) { profiles = decoded }
        favorites = Set(UserDefaults.standard.stringArray(forKey: favoritesKey) ?? [])
    }
    func save(_ profile: SYNM3UProfile79) {
        if let pos = profiles.firstIndex(where: { $0.id == profile.id }) { profiles[pos] = profile }
        else { profiles.append(profile) }
        persist()
    }
    func remove(_ id: UUID) {
        profiles.removeAll { $0.id == id }
        favorites = favorites.filter { !$0.hasPrefix(id.uuidString + "|") }
        UserDefaults.standard.set(Array(favorites), forKey: favoritesKey)
        persist()
    }
    private func persist() {
        if let data = try? JSONEncoder().encode(profiles) { UserDefaults.standard.set(data, forKey: profilesKey) }
    }
    func toggleFavorite(profileID: UUID, channel: SYNM3UChannel79) {
        let key = profileID.uuidString + "|" + channel.id
        if !favorites.insert(key).inserted { favorites.remove(key) }
        UserDefaults.standard.set(Array(favorites), forKey: favoritesKey)
    }
    func favorite(profileID: UUID, channel: SYNM3UChannel79) -> Bool {
        favorites.contains(profileID.uuidString + "|" + channel.id)
    }
    func channelGuide(_ channel: SYNM3UChannel79) -> [SYNM3UProgramme79] {
        let nameKey = Self.normalized(channel.name)
        let idKey = Self.normalized(channel.tvgID)
        return (programmes[idKey] ?? programmes[nameKey] ?? [])
            .filter { $0.end > Date().addingTimeInterval(-3600) }
            .sorted { $0.start < $1.start }
    }
    var groups: [String] { Array(Set(channels.map(\.group))).sorted() }
    func filtered(profileID: UUID) -> [SYNM3UChannel79] {
        channels.filter { ch in
            (category.isEmpty || ch.group == category)
            && (search.isEmpty || ch.name.localizedCaseInsensitiveContains(search))
            && (!favoritesOnly || favorite(profileID: profileID, channel: ch))
        }
    }
    func load(_ profile: SYNM3UProfile79) async {
        loadRevision = UUID()
        let revision = loadRevision
        channels = []; programmes = [:]; notice = nil; loading = true
        category = ""; search = ""; favoritesOnly = false
        defer { if loadRevision == revision { loading = false } }
        do {
            let data = try await Self.readData(profile.playlist, limit: 45_000_000)
            guard loadRevision == revision else { return }
            let text = String(data: data, encoding: .utf8) ?? String(decoding: data, as: UTF8.self)
            let channels = Self.parsePlaylist(text, source: profile.playlist)
            guard !channels.isEmpty else { throw SYNM3UError79.emptyPlaylist }
            self.channels = channels
            if !profile.guide.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                do {
                    var data = try await Self.readData(profile.guide, limit: 45_000_000)
                    if data.starts(with: [0x1f, 0x8b]) { data = try Self.gunzip(data) }
                    let reader = SYNXMLTVParser79()
                    let parsed = try reader.parse(data)
                    if loadRevision == revision { programmes = parsed }
                } catch {
                    if loadRevision == revision { notice = "Canales cargados. Error XMLTV: " + error.localizedDescription }
                }
            }
        } catch {
            if loadRevision == revision { notice = error.localizedDescription }
        }
    }
    static func retainLocalFile(_ file: URL, for id: UUID, ext: String) throws -> String {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("SYN/ImportedLists", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let dest = dir.appendingPathComponent(id.uuidString + "-" + ext)
        let scoped = file.startAccessingSecurityScopedResource()
        defer { if scoped { file.stopAccessingSecurityScopedResource() } }
        guard FileManager.default.fileExists(atPath: file.path) else { throw SYNM3UError79.badFile }
        if FileManager.default.fileExists(atPath: dest.path) { try FileManager.default.removeItem(at: dest) }
        try FileManager.default.copyItem(at: file, to: dest)
        return dest.absoluteString
    }
    private static func readData(_ source: String, limit: Int) async throws -> Data {
        guard let url = URL(string: source), ["https", "http", "file"].contains(url.scheme?.lowercased() ?? "") else {
            throw SYNM3UError79.invalidURL
        }
        if url.isFileURL {
            let attrs = try FileManager.default.attributesOfItem(atPath: url.path)
            if (attrs[.size] as? NSNumber)?.intValue ?? 0 > limit { throw SYNM3UError79.oversize }
            let data = try Data(contentsOf: url)
            guard data.count <= limit else { throw SYNM3UError79.oversize }
            return data
        }
        var request = URLRequest(url: url, cachePolicy: .returnCacheDataElseLoad, timeoutInterval: 40)
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let res = response as? HTTPURLResponse else { throw SYNM3UError79.badFile }
        guard (200..<300).contains(res.statusCode) else { throw SYNM3UError79.badHTTP(res.statusCode) }
        guard data.count <= limit else { throw SYNM3UError79.oversize }
        return data
    }
    private static func gunzip(_ compressed: Data) throws -> Data {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".xml.gz")
        try compressed.write(to: temp)
        defer { try? FileManager.default.removeItem(at: temp) }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/gzip")
        proc.arguments = ["-dc", temp.path]
        let output = Pipe(); proc.standardOutput = output
        proc.standardError = Pipe()
        try proc.run()
        // FileHandle.readDataToEndOfFile prevents pipe deadlocks on large XML files.
        let data = output.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        guard proc.terminationStatus == 0 else { throw SYNM3UError79.xmlInvalid }
        guard data.count <= 180_000_000 else { throw SYNM3UError79.oversize }
        return data
    }
    nonisolated static func normalized(_ name: String) -> String {
        name.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
            .replacingOccurrences(of: #"(?i)^\s*(\|[a-z]{2,3}\||[a-z]{2,3}\s*[:|-])\s*"#, with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
    nonisolated static func parsePlaylist(_ text: String, source: String) -> [SYNM3UChannel79] {
        var result: [SYNM3UChannel79] = []
        var name = "", group = "Sin categoría", icon = "", tvg = ""
        let base = URL(string: source)
        var hasEXTINF = false
        var hls = false
        for raw in text.components(separatedBy: .newlines) {
            let line = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            if line.hasPrefix("#EXT-X-") { hls = true }
            if line.hasPrefix("#EXTINF:") {
                hasEXTINF = true
                let comma = line.lastIndex(of: ",")
                name = comma.map { String(line[line.index(after: $0)...]).trimmingCharacters(in: .whitespacesAndNewlines) } ?? "Canal"
                group = attribute("group-title", in: line) ?? "Sin categoría"
                icon = attribute("tvg-logo", in: line) ?? ""
                tvg = attribute("tvg-id", in: line) ?? attribute("tvg-name", in: line) ?? name
            } else if line.hasPrefix("#EXTGRP:") { group = String(line.dropFirst(8)) }
            else if !line.isEmpty && !line.hasPrefix("#") {
                guard let url = URL(string: line, relativeTo: base)?.absoluteURL,
                      ["http", "https", "rtsp", "rtmp", "udp", "file"].contains(url.scheme?.lowercased() ?? "") else { continue }
                let title = name.isEmpty ? "Canal \(result.count + 1)" : name
                result.append(SYNM3UChannel79(id: String(result.count), name: title, stream: url,
                    group: group, logo: icon.isEmpty ? nil : icon, tvgID: tvg.isEmpty ? title : tvg))
                hasEXTINF = false; name = ""; group = "Sin categoría"; icon = ""; tvg = ""
            }
        }
        // A true HLS media/variant playlist represents ONE stream, not N channels.
        if hls, !text.contains("#EXTINF:-1"), let url = URL(string: source), !url.isFileURL {
            return [SYNM3UChannel79(id: "0", name: "Directo HLS", stream: url, group: "Directo", logo: nil, tvgID: "")]
        }
        _ = hasEXTINF
        return result
    }
    nonisolated private static func attribute(_ key: String, in line: String) -> String? {
        let pattern = NSRegularExpression.escapedPattern(for: key) + #"\s*=\s*["']([^"']*)["']"#
        guard let re = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]),
              let match = re.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)),
              let range = Range(match.range(at: 1), in: line) else { return nil }
        return String(line[range])
    }
}

private final class SYNXMLTVParser79: NSObject, XMLParserDelegate {
    private var result: [String: [SYNM3UProgramme79]] = [:]
    private var channelNames: [String: [String]] = [:]
    private var currentChannel = "", currentID = ""
    private var currentTitle = "", currentDetail = "", currentText = "", inElement = ""
    private var from: Date?, to: Date?
    private var count = 0
    func parse(_ data: Data) throws -> [String: [SYNM3UProgramme79]] {
        let parser = XMLParser(data: data); parser.delegate = self
        guard parser.parse() else { throw SYNM3UError79.xmlInvalid }
        for (channelID, names) in channelNames {
            if let list = result[SYNM3UStore79.normalized(channelID)] {
                for name in names { result[SYNM3UStore79.normalized(name)] = list }
            }
        }
        return result
    }
    func parser(_ parser: XMLParser, didStartElement element: String, namespaceURI: String?, qualifiedName: String?, attributes: [String: String]) {
        inElement = element
        currentText = ""
        if element == "channel" { currentChannel = attributes["id"] ?? "" }
        if element == "programme" {
            currentID = attributes["channel"] ?? ""
            from = Self.xmlDate(attributes["start"] ?? "")
            to = Self.xmlDate(attributes["stop"] ?? "")
            currentTitle = ""; currentDetail = ""
        }
    }
    func parser(_ parser: XMLParser, foundCharacters string: String) { currentText += string }
    func parser(_ parser: XMLParser, didEndElement element: String, namespaceURI: String?, qualifiedName: String?) {
        if element == "display-name" && !currentChannel.isEmpty {
            channelNames[currentChannel, default: []].append(currentText.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        if element == "title" { currentTitle += currentText }
        if element == "desc" { currentDetail += currentText }
        if element == "programme", count < 150_000, let from, let to, to > from {
            let prog = SYNM3UProgramme79(id: "\(currentID)-\(count)", title: currentTitle,
                start: from, end: to, detail: currentDetail)
            result[SYNM3UStore79.normalized(currentID), default: []].append(prog)
            count += 1
        }
        if element == "channel" { currentChannel = "" }
        inElement = ""; currentText = ""
    }
    private static func xmlDate(_ raw: String) -> Date? {
        // XMLTV: 20261028102000 +0100, 20261028102000 or 202610281020 +0100.
        let parts = raw.split(separator: " ", omittingEmptySubsequences: true)
        guard let datePart = parts.first else { return nil }
        let digits = String(datePart)
        let base = String(digits.prefix(14))
        guard base.count >= 12 else { return nil }
        let completed = base.count == 12 ? base + "00" : base
        let fmt = DateFormatter(); fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.dateFormat = "yyyyMMddHHmmss"
        if parts.count > 1 { fmt.timeZone = TimeZone(secondsFromGMT: timezoneSeconds(String(parts[1]))) }
        else { fmt.timeZone = TimeZone.current }
        return fmt.date(from: completed)
    }
    private static func timezoneSeconds(_ s: String) -> Int {
        guard s.count == 5, let hours = Int(s.dropFirst().prefix(2)),
              let mins = Int(s.suffix(2)) else { return 0 }
        return (s.hasPrefix("-") ? -1 : 1) * (hours * 3600 + mins * 60)
    }
}

struct SYNM3UAddSheet79: View {
    @ObservedObject var store: SYNM3UStore79
    let onSave: (SYNM3UProfile79) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = "Mi M3U"
    @State private var isFile = false
    @State private var playlist = ""
    @State private var guide = ""
    @State private var chosenPlaylistFile: URL?
    @State private var chosenGuideFile: URL?
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Nuevo perfil M3U / M3U8").font(.title2.bold())
            Text("Lista IPTV por URL o archivo. La guía XMLTV es opcional y puede ser una URL o un archivo .xml/.xml.gz.")
                .font(.callout).foregroundStyle(.secondary)
            Form {
                TextField("Nombre del perfil", text: $name)
                Picker("Origen de la lista", selection: $isFile) {
                    Text("URL").tag(false); Text("Archivo").tag(true)
                }.pickerStyle(.segmented)
                if isFile {
                    HStack {
                        Text(chosenPlaylistFile?.lastPathComponent ?? "Ningún archivo elegido")
                            .lineLimit(1)
                        Spacer()
                        Button("Elegir M3U…") { chosenPlaylistFile = chooseFile(["m3u", "m3u8", "txt"]) }
                    }
                } else {
                    TextField("https://proveedor/lista.m3u", text: $playlist)
                        .textContentType(.URL)
                }
                HStack {
                    TextField("Guía XMLTV (URL opcional)", text: $guide)
                        .textContentType(.URL)
                    Button("Archivo XMLTV…") { chosenGuideFile = chooseFile(["xml", "gz"]) }
                }
                if let chosenGuideFile { Text(chosenGuideFile.lastPathComponent).font(.caption).foregroundStyle(.secondary) }
            }
            HStack {
                Spacer()
                Button("Cancelar") { dismiss() }
                Button("Guardar perfil") {
                    do {
                        let id = UUID()
                        let source = try chosenPlaylistFile.map { try SYNM3UStore79.retainLocalFile($0, for: id, ext: "m3u") } ?? playlist
                        let xml = try chosenGuideFile.map { try SYNM3UStore79.retainLocalFile($0, for: id, ext: "xmltv") } ?? guide
                        guard !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                              !source.isEmpty else { throw SYNM3UError79.invalidURL }
                        let item = SYNM3UProfile79(id: id, name: name, playlist: source, guide: xml)
                        store.save(item); onSave(item); dismiss()
                    } catch { self.error = error.localizedDescription }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
        .frame(width: 570)
        .alert("No se pudo añadir M3U", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("Entendido", role: .cancel) { error = nil }
        } message: { Text(error ?? "") }
    }
    private func chooseFile(_ types: [String]) -> URL? {
        let picker = NSOpenPanel()
        picker.canChooseFiles = true; picker.canChooseDirectories = false
        picker.allowsMultipleSelection = false
        picker.allowedContentTypes = types.compactMap { UTType(filenameExtension: $0) }
        return picker.runModal() == .OK ? picker.url : nil
    }
}

struct SYNM3UChannelList79: View {
    @ObservedObject var store: SYNM3UStore79
    let profile: SYNM3UProfile79
    let onTune: (SYNM3UChannel79) -> Void
    @State private var selected: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack { Text(profile.name).font(.headline); Spacer(); if store.loading { ProgressView().controlSize(.small) } }
            TextField("Buscar canal…", text: $store.search).textFieldStyle(.roundedBorder)
            HStack {
                Menu {
                    Button("Todas las categorías") { store.category = "" }
                    ForEach(store.groups, id: \.self) { group in Button(group) { store.category = group } }
                } label: { Label(store.category.isEmpty ? "Categorías" : store.category, systemImage: "line.3.horizontal.decrease") }
                Button { store.favoritesOnly.toggle() } label: {
                    Image(systemName: store.favoritesOnly ? "heart.fill" : "heart")
                }.help("Solo favoritos")
            }.buttonStyle(.plain).font(.caption)
            if let notice = store.notice { Text(notice).font(.caption).foregroundStyle(.orange) }
            ScrollView {
                LazyVStack(spacing: 4) {
                    ForEach(store.filtered(profileID: profile.id)) { ch in
                        HStack(spacing: 7) {
                            HStack(spacing: 7) {
                                if let logo = ch.logo, let url = URL(string: logo) {
                                    AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { Color.secondary.opacity(0.12) }
                                        .frame(width: 67, height: 36)
                                        .clipShape(RoundedRectangle(cornerRadius: 7))
                                } else {
                                    Image(systemName: "tv").frame(width: 67, height: 36)
                                }
                                Text(ch.name).font(.system(size: 11)).lineLimit(2)
                                Spacer(minLength: 0)
                            }
                            .contentShape(Rectangle())
                            .gesture(TapGesture(count: 2).exclusively(before: TapGesture(count: 1)).onEnded { value in
                                switch value { case .first: selected = ch.id; onTune(ch)
                                case .second: selected = ch.id }
                            })
                            Button { store.toggleFavorite(profileID: profile.id, channel: ch) } label: {
                                Image(systemName: store.favorite(profileID: profile.id, channel: ch) ? "heart.fill" : "heart")
                            }.buttonStyle(.plain)
                        }
                        .padding(5)
                        .background(selected == ch.id ? Color.accentColor.opacity(0.2) : Color.clear,
                                    in: RoundedRectangle(cornerRadius: 9))
                    }
                }
            }
        }
        .padding(10)
    }
}

struct SYNM3UGuide79: View {
    @ObservedObject var store: SYNM3UStore79
    let profile: SYNM3UProfile79
    let onTune: (SYNM3UChannel79) -> Void
    // nil: guía grande; valor: guía embebida, sin filas cortadas.
    var compactRows7106: Int? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading) {
                    Text("Guía de televisión").font(.title2.bold())
                    Text("XMLTV externa · " + profile.name).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                TextField("Buscar canales…", text: $store.search).frame(width: 210)
            }
            if store.programmes.isEmpty {
                ContentUnavailableView("Guía aún sin programas", systemImage: "calendar",
                    description: Text(store.notice ?? "Añade una URL o un archivo XMLTV al perfil M3U para ver la programación."))
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: compactRows7106 == nil ? 5 : 2) {
                        ForEach(store.filtered(profileID: profile.id)) { channel in
                            HStack(alignment: .center, spacing: 7) {
                                Button { onTune(channel) } label: {
                                    Text(channel.name).font(.caption.weight(.semibold))
                                        .frame(width: 150, alignment: .leading).lineLimit(2)
                                }.buttonStyle(.plain)
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 4) {
                                        ForEach(store.channelGuide(channel).prefix(18)) { programme in
                                            VStack(alignment: .leading, spacing: 4) {
                                                Text(programme.start, style: .time)
                                                    .font(.system(size: 10, weight: .medium))
                                                Text(programme.title)
                                                    .font(.system(size: 12, weight: .semibold)).lineLimit(2)
                                            }
                                            .foregroundStyle(.white)
                                            .padding(7)
                                            .frame(width: CGFloat(max(130, min(330, programme.end.timeIntervalSince(programme.start) / 60 * 3))), height: 55, alignment: .leading)
                                            .background(Color(hue: Double(channel.id.utf8.reduce(0) { ($0 + Int($1)) % 100 }) / 100,
                                                              saturation: 0.58, brightness: 0.62),
                                                        in: RoundedRectangle(cornerRadius: 8))
                                            .help(programme.detail)
                                        }
                                    }
                                }
                            }
                            .frame(height: compactRows7106 == nil ? nil : 60)
                        }
                    }
                }
                .frame(height: compactRows7106.map { CGFloat($0) * 62 })
            }
        }.padding(16)
    }
}

struct SYNM3UEditGuide79: View {
    @ObservedObject var store: SYNM3UStore79
    let profile: SYNM3UProfile79
    let onUpdate: (SYNM3UProfile79) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var source: String = ""
    @State private var chosenFile: URL?
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Guía externa · " + profile.name).font(.title2.bold())
            Text("Pega una URL XMLTV (.xml o .xml.gz), o importa un archivo. Dejar el campo vacío desactiva la guía externa.")
                .font(.caption).foregroundStyle(.secondary)
            TextField("https://proveedor/epg.xml.gz", text: $source)
                .textFieldStyle(.roundedBorder)
            HStack {
                Button("Elegir archivo XMLTV…") {
                    let panel = NSOpenPanel()
                    panel.allowedContentTypes = ["xml", "gz"].compactMap { UTType(filenameExtension: $0) }
                    panel.canChooseDirectories = false
                    if panel.runModal() == .OK { chosenFile = panel.url }
                }
                Text(chosenFile?.lastPathComponent ?? "").font(.caption).foregroundStyle(.secondary)
                Spacer()
            }
            HStack {
                Spacer()
                Button("Cancelar") { dismiss() }
                Button("Guardar") {
                    do {
                        var updated = profile
                        updated.guide = try chosenFile.map { try SYNM3UStore79.retainLocalFile($0, for: profile.id, ext: "xmltv") } ?? source
                        store.save(updated)
                        onUpdate(updated)
                        dismiss()
                    } catch { self.error = error.localizedDescription }
                }.buttonStyle(.borderedProminent)
            }
        }
        .onAppear { source = profile.guide }
        .padding(24).frame(width: 540)
        .alert("No se pudo actualizar la guía", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("Entendido", role: .cancel) { error = nil }
        } message: { Text(error ?? "") }
    }
}
