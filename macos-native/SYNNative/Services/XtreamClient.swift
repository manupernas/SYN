import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct XtreamClient: Sendable {
    let profile: XtreamProfile
    let password: String

    enum APIError: LocalizedError {
        case invalidServer, invalidURL, invalidResponse, invalidAccount, badHTTP(Int), badData
        var errorDescription: String? {
            switch self {
            case .invalidServer: "Servidor Xtream no válido. Usa http:// o https:// y el puerto si corresponde."
            case .invalidURL: "El servidor Xtream devolvió una dirección inválida."
            case .invalidResponse: "El proveedor no devolvió una respuesta Xtream válida."
            case .invalidAccount: "Cuenta Xtream no autorizada, caducada o desactivada."
            case .badHTTP(let code): "El servidor devolvió HTTP \(code)."
            case .badData: "No se pudieron interpretar los datos Xtream."
            }
        }
    }

    // URLComponents preserves an explicit HTTP scheme/port and percent-encodes credentials.
    private var serverURL: URL? {
        let trimmed = profile.server.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let components = URLComponents(string: trimmed),
              let scheme = components.scheme?.lowercased(), ["http", "https"].contains(scheme),
              components.host != nil, components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil else { return nil }
        return components.url
    }

    private func makeURL(endpoint: String, query: [URLQueryItem]) throws -> URL {
        guard let base = serverURL else { throw APIError.invalidServer }
        var c = URLComponents(url: base, resolvingAgainstBaseURL: false)
        let prefix = (c?.percentEncodedPath ?? "").trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        c?.percentEncodedPath = "/" + ([prefix, endpoint].filter { !$0.isEmpty }).joined(separator: "/")
        c?.queryItems = [URLQueryItem(name: "username", value: profile.username),
                         URLQueryItem(name: "password", value: password)] + query
        guard let url = c?.url else { throw APIError.invalidURL }
        return url
    }

    private func fetch<T: Decodable>(_ type: T.Type, action: String? = nil, extra: [URLQueryItem] = []) async throws -> T {
        let actionItem = action.map { [URLQueryItem(name: "action", value: $0)] } ?? []
        let url = try makeURL(endpoint: "player_api.php", query: actionItem + extra)
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 25)
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", forHTTPHeaderField: "User-Agent")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        // Never log request.url; it contains Xtream credentials.
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw APIError.badHTTP(http.statusCode) }
        guard data.count <= 80_000_000 else { throw APIError.badData }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError.badData }
    }

    func authenticate() async throws -> XtreamAccountResponse {
        let account = try await fetch(XtreamAccountResponse.self)
        guard let user = account.userInfo, user.auth?.value == "1",
              user.status?.lowercased() != "disabled",
              user.status?.lowercased() != "expired",
              user.status?.lowercased() != "banned" else { throw APIError.invalidAccount }
        return account
    }
    func liveCategories() async throws -> [XtreamCategory] {
        try await fetch([XtreamCategory].self, action: "get_live_categories")
    }
    func liveStreams(category: String? = nil) async throws -> [LiveStream] {
        try await fetch([LiveStream].self, action: "get_live_streams", extra: category.map { [URLQueryItem(name: "category_id", value: $0)] } ?? [])
    }
    func movieCategories() async throws -> [XtreamCategory] {
        try await fetch([XtreamCategory].self, action: "get_vod_categories")
    }
    func movies(category: String? = nil) async throws -> [MovieStream] {
        try await fetch([MovieStream].self, action: "get_vod_streams", extra: category.map { [URLQueryItem(name: "category_id", value: $0)] } ?? [])
    }
    func seriesCategories() async throws -> [XtreamCategory] {
        try await fetch([XtreamCategory].self, action: "get_series_categories")
    }
    func series(category: String? = nil) async throws -> [SeriesStream] {
        try await fetch([SeriesStream].self, action: "get_series", extra: category.map { [URLQueryItem(name: "category_id", value: $0)] } ?? [])
    }
    func episodes(seriesID: String) async throws -> [SeriesEpisode] {
        try await fetch(SeriesInfoResponse.self, action: "get_series_info", extra: [URLQueryItem(name: "series_id", value: seriesID)]).allEpisodes()
    }
    func epg(streamID: String, limit: Int = 96) async throws -> [EPGEntry] {
        try await fetch(EPGResponse.self, action: "get_short_epg", extra: [URLQueryItem(name: "stream_id", value: streamID), URLQueryItem(name: "limit", value: String(limit))]).epgListings ?? []
    }

    // SYN_NATIVE_EPG_35: tabla completa EPG cuando el servidor Xtream la ofrece.
    func epgFull(streamID: String) async throws -> [EPGEntry] {
        try await fetch(EPGResponse.self, action: "get_simple_data_table", extra: [URLQueryItem(name: "stream_id", value: streamID)]).epgListings ?? []
    }

    // Build literal stream paths after percent encoding each segment (never leak in logs).
    private func mediaURL(kind: String, id: String, ext: String) throws -> URL {
        guard let base = serverURL else { throw APIError.invalidServer }
        let safe = CharacterSet.urlPathAllowed.subtracting(CharacterSet(charactersIn: "/?#%"))
        let pieces = [kind, profile.username, password, id + "." + ext].map {
            $0.addingPercentEncoding(withAllowedCharacters: safe) ?? ""
        }
        var components = URLComponents(url: base, resolvingAgainstBaseURL: false)
        let prefix = (components?.percentEncodedPath ?? "").trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        components?.percentEncodedPath = "/" + ([prefix] + pieces).filter { !$0.isEmpty }.joined(separator: "/")
        guard let url = components?.url else { throw APIError.invalidURL }
        return url
    }
    func liveURL(_ stream: LiveStream) throws -> URL {
        try mediaURL(kind: "live", id: stream.id, ext: profile.output.rawValue)
    }
    func movieURL(_ movie: MovieStream) throws -> URL {
        try mediaURL(kind: "movie", id: movie.id, ext: (movie.containerExtension ?? "mp4").safeFileExtension)
    }
    func episodeURL(_ episode: SeriesEpisode) throws -> URL {
        try mediaURL(kind: "series", id: episode.id.value, ext: (episode.containerExtension ?? "mp4").safeFileExtension)
    }
}
