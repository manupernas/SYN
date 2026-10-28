import AppKit
import SwiftUI

// SYN 7.6 · Cartelera. Independiente de VLCKit, REC, DVR y del servicio Xtream.
struct SYNPosterItem76: Identifiable {
    let id: String
    let title: String
    let posterURL: String?
    let categoryID: String
    let categoryName: String
}

struct SYNPosterCategory76: Identifiable {
    let id: String
    let name: String
}

@MainActor
private enum SYNPosterImageCache76 {
    static let cache = NSCache<NSString, NSImage>()
    static let userAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    static func load(_ rawURL: String?) async -> NSImage? {
        guard let rawURL = rawURL?.trimmingCharacters(in: .whitespacesAndNewlines),
              let url = URL(string: rawURL),
              ["http", "https"].contains(url.scheme?.lowercased() ?? "") else { return nil }
        if let saved = cache.object(forKey: rawURL as NSString) { return saved }
        var request = URLRequest(url: url, cachePolicy: .returnCacheDataElseLoad, timeoutInterval: 16)
        request.setValue(userAgent, forHTTPHeaderField: "User-Agent")
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              let response = response as? HTTPURLResponse,
              (200..<300).contains(response.statusCode),
              data.count > 32 && data.count < 12_000_000,
              let image = NSImage(data: data),
              image.size.width > 1 && image.size.height > 1 else { return nil }
        cache.setObject(image, forKey: rawURL as NSString)
        return image
    }
}

private struct SYNGeneratedPoster76: View {
    let title: String
    let series: Bool

    private var hash: UInt64 {
        title.utf8.reduce(UInt64(14695981039346656037)) {
            ($0 ^ UInt64($1)) &* UInt64(1099511628211)
        }
    }
    private var hue: Double { Double(hash % 360) / 360 }

    var body: some View {
        GeometryReader { g in
            let w = g.size.width
            let h = g.size.height
            ZStack {
                LinearGradient(colors: [
                    Color(hue: hue, saturation: 0.55, brightness: 0.42),
                    Color(hue: (hue + 0.12).truncatingRemainder(dividingBy: 1), saturation: 0.62, brightness: 0.19)
                ], startPoint: .topLeading, endPoint: .bottomTrailing)
                Circle()
                    .fill(Color(hue: (hue + 0.09).truncatingRemainder(dividingBy: 1), saturation: 0.33, brightness: 0.89).opacity(0.40))
                    .frame(width: w * 0.88, height: w * 0.88)
                    .offset(x: w * 0.20, y: -h * 0.18)
                Circle()
                    .fill(Color(hue: (hue + 0.17).truncatingRemainder(dividingBy: 1), saturation: 0.30, brightness: 0.96).opacity(0.68))
                    .frame(width: w * 0.39, height: w * 0.39)
                    .offset(x: -w * 0.12, y: -h * 0.10)
                Path { path in
                    path.move(to: CGPoint(x: 0, y: h * 0.64))
                    path.addLine(to: CGPoint(x: w * 0.45, y: h * 0.47))
                    path.addLine(to: CGPoint(x: w, y: h * 0.70))
                    path.addLine(to: CGPoint(x: w, y: h))
                    path.addLine(to: CGPoint(x: 0, y: h))
                }
                .fill(Color.black.opacity(0.28))
                Path { path in
                    path.move(to: CGPoint(x: 0, y: h * 0.81))
                    path.addLine(to: CGPoint(x: w * 0.62, y: h * 0.67))
                    path.addLine(to: CGPoint(x: w, y: h * 0.78))
                    path.addLine(to: CGPoint(x: w, y: h))
                    path.addLine(to: CGPoint(x: 0, y: h))
                }
                .fill(Color.black.opacity(0.34))
                VStack(alignment: .leading, spacing: 0) {
                    HStack {
                        Text(series ? "SYN / SERIES" : "SYN / CINE")
                            .font(.system(size: 9, weight: .heavy, design: .rounded))
                            .tracking(1.6)
                        Spacer()
                    }
                    Spacer()
                    Text(title)
                        .font(.system(size: min(17, max(12, w * 0.11)), weight: .heavy, design: .rounded))
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                        .shadow(color: .black.opacity(0.5), radius: 3)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(.orange)
                        .frame(width: w * 0.31, height: 3)
                        .padding(.top, 8)
                }
                .foregroundStyle(.white)
                .padding(13)
            }
            .frame(width: w, height: h)
            .clipped()
        }
        .accessibilityLabel("Portada ilustrada de \(title)")
    }
}

private struct SYNPosterCard76: View {
    let item: SYNPosterItem76
    let series: Bool
    let onOpen: () -> Void
    @State private var image: NSImage?
    @State private var imageRequestFinished = false

    // SYN_761_SERIES_FALLBACK_HORIZONTAL
    // Las series sin imagen válida usan ilustración horizontal 4:3.
    // Al descargar una portada real mantenemos 2:3 hasta terminar la petición
    // para no hacer que cada cartel cambie de forma durante la carga.
    private var hasPosterURL: Bool {
        guard let raw = item.posterURL?.trimmingCharacters(in: .whitespacesAndNewlines),
              let url = URL(string: raw) else { return false }
        return ["http", "https"].contains(url.scheme?.lowercased() ?? "")
    }

    private var compactSeriesFallback: Bool {
        series && image == nil && (!hasPosterURL || imageRequestFinished)
    }

    var body: some View {
        Button(action: onOpen) {
            VStack(alignment: .leading, spacing: 7) {
                ZStack {
                    SYNGeneratedPoster76(title: item.title, series: series)
                    if let image {
                        GeometryReader { size in
                            Image(nsImage: image)
                                .resizable()
                                .scaledToFill()
                                .frame(width: size.size.width, height: size.size.height)
                                .clipped()
                        }
                        .accessibilityLabel("Carátula de \(item.title)")
                    }
                }
                // Películas y carátulas reales: formato cartel 2:3.
                // Series sin imagen: ilustración más compacta y horizontal 4:3.
                .aspectRatio(compactSeriesFallback ? 4.0 / 3.0 : 2.0 / 3.0, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                Text(item.title)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text(item.categoryName.isEmpty ? (series ? "Serie" : "Película") : item.categoryName)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(8)
            .frame(maxWidth: .infinity, alignment: .topLeading)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 15))
            .overlay(RoundedRectangle(cornerRadius: 15).strokeBorder(.primary.opacity(0.10)))
        }
        .buttonStyle(.plain)
        .task(id: item.id + ":" + (item.posterURL ?? "")) {
            imageRequestFinished = false
            image = nil
            let downloaded = await SYNPosterImageCache76.load(item.posterURL)
            guard !Task.isCancelled else { return }
            image = downloaded
            imageRequestFinished = true
        }
    }
}

struct SYNPosterGallery76: View {
    let series: Bool
    let items: [SYNPosterItem76]
    let categories: [SYNPosterCategory76]
    @Binding var query: String
    @Binding var categoryID: String
    let onBack: () -> Void
    let onOpen: (String) -> Void

    private var heading: String { series ? "Series" : "Cine" }

    var body: some View {
        HStack(spacing: 0) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 4) {
                    categoryButton("Todas las categorías", id: "")
                    ForEach(categories) { entry in
                        categoryButton(entry.name, id: entry.id)
                    }
                }
                .padding(10)
            }
            .frame(width: 184)
            .background(Color(nsColor: .underPageBackgroundColor).opacity(0.7))
            Divider()
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    Button(action: onBack) {
                        Label("Perfil", systemImage: "chevron.left")
                    }
                    .buttonStyle(.bordered)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("SYN / TU BIBLIOTECA")
                            .font(.system(size: 10, weight: .bold))
                            .tracking(1.6)
                            .foregroundStyle(.orange)
                        Text(heading)
                            .font(.system(size: 25, weight: .bold))
                    }
                    Spacer()
                    TextField("Buscar títulos…", text: $query)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 245)
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 16)
                Divider()
                if items.isEmpty {
                    ContentUnavailableView(
                        query.isEmpty ? "No hay títulos en esta categoría" : "No se encontraron resultados",
                        systemImage: "rectangle.stack",
                        description: Text("Selecciona otra categoría o cambia la búsqueda.")
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ScrollView {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 145, maximum: 195), spacing: 14, alignment: .top)], alignment: .leading, spacing: 16) {
                            ForEach(items) { item in
                                SYNPosterCard76(item: item, series: series) {
                                    onOpen(item.id)
                                }
                            }
                        }
                        .padding(18)
                    }
                    .scrollIndicators(.visible)
                }
            }
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private func categoryButton(_ title: String, id: String) -> some View {
        Button { categoryID = id } label: {
            HStack {
                Text(title).lineLimit(1)
                Spacer(minLength: 2)
            }
            .font(.system(size: 11, weight: categoryID == id ? .semibold : .regular))
            .padding(.horizontal, 9)
            .padding(.vertical, 9)
            .foregroundStyle(categoryID == id ? Color.primary : Color.secondary)
            .background(categoryID == id ? Color.accentColor.opacity(0.16) : Color.clear,
                        in: RoundedRectangle(cornerRadius: 9))
        }
        .buttonStyle(.plain)
        .help(title)
    }
}
