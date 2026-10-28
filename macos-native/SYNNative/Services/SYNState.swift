import Foundation
import Combine

@MainActor final class SYNState: ObservableObject {
    enum Section: String, CaseIterable, Identifiable {
        case tv = "TV", favorites = "Favoritos", movies = "Cine", series = "Series", epg = "Guía", dvr = "DVR"
        var id: String { rawValue }
        var symbol: String {
            switch self { case .tv: "tv"; case .favorites: "heart.fill"; case .movies: "film"; case .series: "rectangle.stack"; case .epg: "calendar"; case .dvr: "record.circle" }
        }
    }
    @Published var section: Section = .tv {
        didSet {
            // TV y Favoritos comparten el catálogo Xtream.
            // No borrar ni descargar canales al alternar.
            let tvSections: Set<Section> = [.tv, .favorites]

            if tvSections.contains(oldValue),
               tvSections.contains(section),
               !channels.isEmpty {
                chosenCategory = ""
                return
            }

            loadCurrentSection()
        }
    }
    @Published var selectedProfile: XtreamProfile?
    @Published var categories: [XtreamCategory] = []
    @Published var chosenCategory: String = ""
    @Published var channels: [LiveStream] = []
    @Published var movies: [MovieStream] = []
    @Published var shows: [SeriesStream] = []
    @Published var episodes: [SeriesEpisode] = []
    @Published var chosenShow: SeriesStream?
    @Published var epg: [EPGEntry] = []
    @Published var playingURL: URL?
    @Published var playingTitle = "Selecciona un canal"
    @Published var query = ""
    @Published var status = "Añade una fuente para comenzar"
    @Published var busy = false
    @Published var error: String?
    @Published var favorites: Set<String> = Set(UserDefaults.standard.stringArray(forKey: "syn.native.favorites.v1") ?? [])
    private var generation = 0

    var client: XtreamClient? {
        guard let selectedProfile, let password = CredentialVault.password(id: selectedProfile.id) else { return nil }
        return XtreamClient(profile: selectedProfile, password: password)
    }
    func select(_ profile: XtreamProfile) {
        selectedProfile = profile
        playingURL = nil
        categories = []; channels = []; movies = []; shows = []; episodes = []; epg = []
        section = .tv
    }
    func loadCurrentSection() {
        generation += 1
        let token = generation
        categories = []; chosenCategory = ""
        channels = []; movies = []; shows = []; episodes = []
        guard let client else { return }
        guard section != .dvr else { busy = false; return }
        busy = true
        error = nil
        status = "Cargando \(section.rawValue)…"
        Task {
            do {
                switch section {
                case .tv, .favorites, .epg:
                    async let cats = client.liveCategories()
                    async let entries = client.liveStreams()
                    let (a, b) = try await (cats, entries)
                    guard token == generation else { return }
                    categories = a; channels = b
                    status = "\(b.count) canales Xtream"
                case .movies:
                    async let cats = client.movieCategories()
                    async let entries = client.movies()
                    let (a, b) = try await (cats, entries)
                    guard token == generation else { return }
                    categories = a; movies = b; status = "\(b.count) películas"
                case .series:
                    async let cats = client.seriesCategories()
                    async let entries = client.series()
                    let (a, b) = try await (cats, entries)
                    guard token == generation else { return }
                    categories = a; shows = b; status = "\(b.count) series"
                case .dvr: break
                }
            } catch {
                guard token == generation else { return }
                self.error = error.localizedDescription
                status = "Error al consultar Xtream"
            }
            if token == generation { busy = false }
        }
    }
    func filtered(_ category: FlexibleID?) -> Bool {
        chosenCategory.isEmpty || category?.value == chosenCategory
    }
    var visibleChannels: [LiveStream] {
        channels.filter { filtered($0.categoryID) && (query.isEmpty || $0.name.localizedCaseInsensitiveContains(query)) }
    }
    var visibleMovies: [MovieStream] {
        movies.filter { filtered($0.categoryID) && (query.isEmpty || $0.name.localizedCaseInsensitiveContains(query)) }
    }
    var visibleShows: [SeriesStream] {
        shows.filter { filtered($0.categoryID) && (query.isEmpty || $0.name.localizedCaseInsensitiveContains(query)) }
    }
    func tune(_ ch: LiveStream) {
        guard let client else { return }
        do {
            playingURL = try client.liveURL(ch)
            playingTitle = ch.name
            epg = []
            status = "Reproduciendo · VLC · \(ch.name)"
            Task {
                if let entries = try? await client.epg(streamID: ch.id), playingTitle == ch.name { epg = entries }
            }
        } catch { self.error = error.localizedDescription }
    }
    func tune(_ film: MovieStream) {
        guard let client else { return }
        do { playingURL = try client.movieURL(film); playingTitle = film.name; epg = [] }
        catch { self.error = error.localizedDescription }
    }
    func loadEpisodes(_ show: SeriesStream) {
        chosenShow = show; episodes = []
        guard let client else { return }
        Task {
            do {
                let result = try await client.episodes(seriesID: show.id)
                if chosenShow?.id == show.id { episodes = result }
            } catch { self.error = error.localizedDescription }
        }
    }
    func tune(_ episode: SeriesEpisode) {
        guard let client else { return }
        do {
            playingURL = try client.episodeURL(episode)
            playingTitle = episode.title ?? "Episodio \(episode.episodeNum?.value ?? "0")"
            epg = []
        } catch { self.error = error.localizedDescription }
    }
    func favoriteKey(_ id: String) -> String {
        "\(selectedProfile?.id.uuidString ?? "no-profile"):\(id)"
    }
    func isFavorite(_ ch: LiveStream) -> Bool { favorites.contains(favoriteKey(ch.id)) }
    func toggleFavorite(_ ch: LiveStream) {
        let key = favoriteKey(ch.id)
        if favorites.contains(key) { favorites.remove(key) } else { favorites.insert(key) }
        UserDefaults.standard.set(Array(favorites), forKey: "syn.native.favorites.v1")
    }
}
