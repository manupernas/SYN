import Foundation

// SYN_DVR_PLUG_PLAY_446: autodiscovery and first-run installation of the runtime.
// No Homebrew, Python, LaunchAgent or terminal command is required for the end user.
// No recorder / job files are altered here.
enum SYNBundledRuntime446 {
    private static var resources: URL? { Bundle.main.resourceURL?.appendingPathComponent("SYN-DVR-Runtime", isDirectory: true) }
    private static var macOS: URL? { Bundle.main.executableURL?.deletingLastPathComponent() }

    static var python: URL? {
        guard let url = macOS?.appendingPathComponent("syn-dvr-python"),
              FileManager.default.isExecutableFile(atPath: url.path) else { return nil }
        return url
    }
    static var supervisor: URL? {
        guard let url = resources?.appendingPathComponent("standalone_supervisor.py"),
              FileManager.default.fileExists(atPath: url.path) else { return nil }
        return url
    }
    static var remote: URL? {
        guard let url = resources?.appendingPathComponent("syn_dvr_remote.py"),
              FileManager.default.fileExists(atPath: url.path) else { return nil }
        return url
    }
    static var available: Bool {
        guard python != nil, supervisor != nil, remote != nil, let macOS else { return false }
        let fm = FileManager.default
        return ["syn-dvr-worker", "ffmpeg", "ffprobe", "comskip", "syn-dvr-ads"].allSatisfy {
            fm.isExecutableFile(atPath: macOS.appendingPathComponent($0).path)
        }
    }

    private static func deploy(_ source: URL, to destination: URL) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        // Preserve an existing installation rather than overwrite a running worker.
        if fm.fileExists(atPath: destination.path) { return }
        let staged = destination.deletingLastPathComponent().appendingPathComponent(".syn-dvr-446-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: staged) }
        try fm.copyItem(at: source, to: staged)
        try fm.moveItem(at: staged, to: destination)
    }

    static func prepare() throws {
        guard available, let macOS, let resources else {
            throw NSError(domain: "SYN DVR", code: 446,
                          userInfo: [NSLocalizedDescriptionKey: "El paquete autónomo está incompleto."])
        }
        let fm = FileManager.default
        let home = fm.homeDirectoryForCurrentUser
        let bin = home.appendingPathComponent("Library/Application Support/SYN Native DVR/bin", isDirectory: true)
        let remoteDir = home.appendingPathComponent("Library/Application Support/SYN DVR Remote", isDirectory: true)
        let engineDir = home.appendingPathComponent("Library/Application Support/SYN DVR Engine 2.0", isDirectory: true)
        try deploy(macOS.appendingPathComponent("syn-dvr-worker"), to: bin.appendingPathComponent("syn-dvr-worker"))
        try deploy(resources.appendingPathComponent("standalone_supervisor.py"), to: remoteDir.appendingPathComponent("standalone_supervisor.py"))
        try deploy(resources.appendingPathComponent("syn_dvr_remote.py"), to: remoteDir.appendingPathComponent("syn_dvr_remote.py"))
        try deploy(resources.appendingPathComponent("hls_server.py"), to: engineDir.appendingPathComponent("hls_server.py"))
    }

    static func environment() -> [String: String] {
        var result = ProcessInfo.processInfo.environment
        guard let macOS, let resources, let python else { return result }
        let engine = macOS.appendingPathComponent("syn-dvr-worker").path
        result["SYN_DVR_V2_FFMPEG"] = macOS.appendingPathComponent("ffmpeg").path
        result["SYN_DVR_V2_REMUX_FFMPEG"] = macOS.appendingPathComponent("ffmpeg").path
        result["SYN_DVR_V2_FFPROBE"] = macOS.appendingPathComponent("ffprobe").path
        result["SYN_DVR_POOL_PYTHON"] = python.path
        result["SYN_DVR_POOL_SERVER"] = resources.appendingPathComponent("hls_server.py").path
        result["SYN_DVR_ENGINE"] = engine
        result["SYN_DVR_WORKER"] = engine
        result["SYN_DVR_REMOTE_SCRIPT"] = resources.appendingPathComponent("syn_dvr_remote.py").path
        // External Python and Homebrew are NOT in the runtime PATH.
        result["PATH"] = macOS.path + ":/usr/bin:/bin:/usr/sbin:/sbin"
        return result
    }
}
