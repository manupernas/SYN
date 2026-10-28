import Foundation

// Xtream panels frequently mix numeric and textual IDs.
struct FlexibleID: Codable, Hashable, Sendable {
    let value: String
    init(_ value: String) { self.value = value }
    init(from decoder: Decoder) throws {
        let box = try decoder.singleValueContainer()
        if let text = try? box.decode(String.self) { value = text }
        else if let number = try? box.decode(Int.self) { value = String(number) }
        else if let flag = try? box.decode(Bool.self) { value = flag ? "1" : "0" }
        else { throw DecodingError.typeMismatch(String.self, .init(codingPath: decoder.codingPath, debugDescription: "ID inválido")) }
    }
    func encode(to encoder: Encoder) throws { var box = encoder.singleValueContainer(); try box.encode(value) }
}

struct XtreamCategory: Decodable, Identifiable, Hashable {
    let categoryID: FlexibleID
    let categoryName: String
    var id: String { categoryID.value }
    enum CodingKeys: String, CodingKey { case categoryID = "category_id", categoryName = "category_name" }
}

struct LiveStream: Decodable, Identifiable, Hashable {
    let streamID: FlexibleID
    let name: String
    let categoryID: FlexibleID?
    let streamIcon: String?
    let epgChannelID: String?
    var id: String { streamID.value }
    enum CodingKeys: String, CodingKey {
        case streamID = "stream_id", name, categoryID = "category_id"
        case streamIcon = "stream_icon", epgChannelID = "epg_channel_id"
    }
}

struct MovieStream: Decodable, Identifiable, Hashable {
    let streamID: FlexibleID
    let name: String
    let categoryID: FlexibleID?
    let streamIcon: String?
    let containerExtension: String?
    var id: String { streamID.value }
    enum CodingKeys: String, CodingKey {
        case streamID = "stream_id", name, categoryID = "category_id"
        case streamIcon = "stream_icon", containerExtension = "container_extension"
    }
}

struct SeriesStream: Decodable, Identifiable, Hashable {
    let seriesID: FlexibleID
    let name: String
    let categoryID: FlexibleID?
    let cover: String?
    var id: String { seriesID.value }
    enum CodingKeys: String, CodingKey { case seriesID = "series_id", name, categoryID = "category_id", cover }
}

struct SeriesEpisode: Decodable, Identifiable, Hashable {
    let id: FlexibleID
    let title: String?
    let containerExtension: String?
    let episodeNum: FlexibleID?
    enum CodingKeys: String, CodingKey { case id, title, containerExtension = "container_extension", episodeNum = "episode_num" }
}

struct SeriesInfoResponse: Decodable {
    let episodes: [String: [SeriesEpisode]]?
    func allEpisodes() -> [SeriesEpisode] {
        (episodes ?? [:]).keys.sorted { (Int($0) ?? 0) < (Int($1) ?? 0) }.flatMap { episodes?[$0] ?? [] }
    }
}

struct EPGResponse: Decodable {
    let epgListings: [EPGEntry]?
    enum CodingKeys: String, CodingKey { case epgListings = "epg_listings" }
}

struct EPGEntry: Decodable, Identifiable {
    let id: FlexibleID?
    let title: String?
    let description: String?
    let start: String?
    let end: String?
    let startTimestamp: FlexibleID?
    let stopTimestamp: FlexibleID?
    enum CodingKeys: String, CodingKey {
        case id, title, description, start, end
        case startTimestamp = "start_timestamp", stopTimestamp = "stop_timestamp"
        case category, genre, rating, ageRating = "age_rating", cast, actors, presenter, presenters, director, country, year
    }
    // SYN_EPG_METADATA_39: los metadatos extendidos son opcionales y varían por proveedor.
    let category: String?
    let genre: String?
    let rating: String?
    let ageRating: String?
    let cast: String?
    let actors: String?
    let presenter: String?
    let presenters: String?
    let director: String?
    let country: String?
    let year: String?

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func read(_ key: CodingKeys) -> String? {
            if let text = try? c.decode(String.self, forKey: key) { return text }
            if let number = try? c.decode(Double.self, forKey: key) { return String(number) }
            if let names = try? c.decode([String].self, forKey: key) { return names.joined(separator: ", ") }
            return nil
        }
        id = try? c.decode(FlexibleID.self, forKey: .id)
        title = read(.title)
        description = read(.description)
        start = read(.start)
        end = read(.end)
        startTimestamp = try? c.decode(FlexibleID.self, forKey: .startTimestamp)
        stopTimestamp = try? c.decode(FlexibleID.self, forKey: .stopTimestamp)
        category = read(.category); genre = read(.genre)
        rating = read(.rating); ageRating = read(.ageRating)
        cast = read(.cast); actors = read(.actors)
        presenter = read(.presenter); presenters = read(.presenters)
        director = read(.director); country = read(.country); year = read(.year)
    }
    var categoryText: String { Self.decodeMaybeBase64(category ?? genre) }
    var ratingText: String { Self.decodeMaybeBase64(rating ?? ageRating) }
    var peopleText: String { Self.decodeMaybeBase64(presenters ?? presenter ?? cast ?? actors) }
    var titleText: String { Self.decodeMaybeBase64(title) }
    var descriptionText: String { Self.decodeMaybeBase64(description) }
    static func decodeMaybeBase64(_ raw: String?) -> String {
        guard let raw, !raw.isEmpty else { return "" }
        // Avoid decoding ordinary short strings accidentally.
        if raw.count >= 8, raw.count % 4 == 0,
           let data = Data(base64Encoded: raw),
           let decoded = String(data: data, encoding: .utf8),
           decoded.unicodeScalars.allSatisfy({ $0.properties.generalCategory != .control || $0.value == 10 }) {
            return decoded
        }
        return raw
    }
}

struct XtreamProfile: Codable, Identifiable, Hashable {
    let id: UUID
    var name: String
    var server: String
    var username: String
    var output: StreamOutput
    enum StreamOutput: String, Codable, CaseIterable { case ts, m3u8 }
}

struct ProfileCredentials: Codable {
    let username: String
    let password: String
}

struct XtreamAccountResponse: Decodable {
    struct UserInfo: Decodable {
        let auth: FlexibleID?
        let status: String?
        let maxConnections: FlexibleID?
        let activeConnections: FlexibleID?
        enum CodingKeys: String, CodingKey {
            case auth, status, maxConnections = "max_connections", activeConnections = "active_cons"
        }
    }
    let userInfo: UserInfo?
    enum CodingKeys: String, CodingKey { case userInfo = "user_info" }
}

extension String {
    var safeFileExtension: String {
        let value = lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        return ["mp4", "mkv", "avi", "mov", "ts", "m3u8"].contains(value) ? value : "mp4"
    }
}
