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
        return ["syn-dvr-worker", "ffmpeg", "ffprobe"].allSatisfy {
            fm.isExecutableFile(atPath: macOS.appendingPathComponent($0).path)
        }
    }

    // 454: solamente datos y configuracion en la cuenta actual. No instalar
    // motores/binarios en Application Support, ni usar sudo ni tocar permisos ajenos.
    static func prepare() throws {
        guard available else {
            throw NSError(domain: "SYN DVR", code: 454,
                          userInfo: [NSLocalizedDescriptionKey: "Faltan componentes esenciales dentro de SYN DVR.app."])
        }
        let fm = FileManager.default
        let home = fm.homeDirectoryForCurrentUser
        let base = home.appendingPathComponent("Library/Application Support", isDirectory: true)
        let engine = base.appendingPathComponent("SYN DVR Engine 2.0", isDirectory: true)
        let remote = base.appendingPathComponent("SYN DVR Remote", isDirectory: true)
        let recordings = home.appendingPathComponent("Movies/SYN Grabaciones", isDirectory: true)
        // No cambiar propietario/permisos de ~/Library ni de Application Support.
        for directory in [engine, engine.appendingPathComponent("jobs", isDirectory: true), remote, recordings] {
            try fm.createDirectory(at: directory, withIntermediateDirectories: true,
                                   attributes: [.posixPermissions: NSNumber(value: 0o700)])
        }
        let config = remote.appendingPathComponent("server.json")
        if !fm.fileExists(atPath: config.path) {
            let values: [String: Any] = ["bind": "127.0.0.1", "port": 8090,
                                          "recordingsFolder": recordings.path,
                                          "authRequired": false,
                                          "createdAt": Date().timeIntervalSince1970]
            let data = try JSONSerialization.data(withJSONObject: values, options: [.sortedKeys])
            try data.write(to: config, options: .atomic)
            try fm.setAttributes([.posixPermissions: NSNumber(value: 0o600)], ofItemAtPath: config.path)
        }
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
