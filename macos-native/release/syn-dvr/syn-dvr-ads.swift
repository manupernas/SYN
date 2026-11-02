import Foundation

// SYN_DVR_ADS_443 — herramienta nativa: sin Python, Homebrew ni cambios al MKV original.
// Mantiene el protocolo OK|ruta / NONE|motivo / ERROR|motivo que ya espera SYN DVR.
struct ProcessingFailure: Error, CustomStringConvertible {
    let message: String
    var description: String { message }
    init(_ message: String) { self.message = message }
}

func processRun(_ executable: String, _ args: [String], timeout: TimeInterval = 7200) throws -> String {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: executable)
    task.arguments = args
    let logFile = FileManager.default.temporaryDirectory.appendingPathComponent("syn-ads-cmd-\(UUID().uuidString).log")
    FileManager.default.createFile(atPath: logFile.path, contents: nil)
    let log = try FileHandle(forWritingTo: logFile)
    defer {
        try? log.close()
        try? FileManager.default.removeItem(at: logFile)
    }
    task.standardOutput = log
    task.standardError = log
    task.standardInput = FileHandle.nullDevice
    let completed = DispatchSemaphore(value: 0)
    task.terminationHandler = { _ in completed.signal() }
    do { try task.run() } catch {
        throw ProcessingFailure("No se pudo ejecutar \(URL(fileURLWithPath: executable).lastPathComponent): \(error.localizedDescription)")
    }
    if completed.wait(timeout: .now() + timeout) == .timedOut {
        if task.isRunning { task.terminate() }
        _ = completed.wait(timeout: .now() + 5)
        throw ProcessingFailure("Se agotó el tiempo de ejecución de \(URL(fileURLWithPath: executable).lastPathComponent).")
    }
    let output = (try? String(contentsOf: logFile, encoding: .utf8)) ?? ""
    if task.terminationStatus != 0 {
        throw ProcessingFailure("\(URL(fileURLWithPath: executable).lastPathComponent) terminó con error \(task.terminationStatus): \(String(output.suffix(300)))")
    }
    return output
}

func duration(_ video: URL, _ ffprobe: String) throws -> Double {
    let output = try processRun(ffprobe, ["-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=noprint_wrappers=1:nokey=1", video.path], timeout: 90)
    guard let seconds = Double(output.trimmingCharacters(in: .whitespacesAndNewlines)),
          seconds.isFinite && seconds > 0 else {
        throw ProcessingFailure("El archivo no tiene una duración válida.")
    }
    return seconds
}

struct Interval {
    var start: Double
    var end: Double
    var length: Double { end - start }
}

func readCuts(_ edl: URL, total: Double) throws -> [Interval] {
    let data = try String(contentsOf: edl, encoding: .utf8)
    var cuts: [Interval] = []
    for line in data.components(separatedBy: .newlines) {
        let parts = line.split(whereSeparator: { $0.isWhitespace })
        guard parts.count >= 3, parts[2] == "0",
              let start = Double(parts[0]), let end = Double(parts[1]),
              start.isFinite, end.isFinite else { continue }
        let a = max(0, start), b = min(total, end)
        if b > a + 0.3 { cuts.append(Interval(start: a, end: b)) }
    }
    cuts.sort { $0.start < $1.start }
    var merged: [Interval] = []
    for cut in cuts {
        if let last = merged.last, cut.start <= last.end + 0.1 {
            merged[merged.count - 1].end = max(last.end, cut.end)
        } else { merged.append(cut) }
    }
    return merged
}

func keepParts(_ cuts: [Interval], total: Double) -> [Interval] {
    var parts: [Interval] = []
    var position = 0.0
    for cut in cuts {
        if cut.start - position >= 0.4 { parts.append(Interval(start: position, end: cut.start)) }
        position = max(position, cut.end)
    }
    if total - position >= 0.4 { parts.append(Interval(start: position, end: total)) }
    return parts
}

func outputPath(_ original: URL) throws -> URL {
    let fm = FileManager.default
    let parent = original.deletingLastPathComponent()
    let base = original.deletingPathExtension().lastPathComponent
    let first = parent.appendingPathComponent("\(base) - sin anuncios.mkv")
    if !fm.fileExists(atPath: first.path) { return first }
    for number in 2...999 {
        let candidate = parent.appendingPathComponent("\(base) - sin anuncios \(number).mkv")
        if !fm.fileExists(atPath: candidate.path) { return candidate }
    }
    throw ProcessingFailure("Demasiadas copias existentes para este vídeo.")
}

func cleanAds(_ original: URL, comskip: String, ffmpeg: String, ffprobe: String) throws -> (String, String) {
    let fm = FileManager.default
    guard fm.fileExists(atPath: original.path),
          ["mkv", "mp4", "ts", "mov"].contains(original.pathExtension.lowercased()) else {
        throw ProcessingFailure("El archivo original no existe o el formato no es compatible.")
    }
    let total = try duration(original, ffprobe)
    if total < 120 { return ("NONE", "La grabación es demasiado corta para buscar anuncios.") }
    let work = fm.temporaryDirectory.appendingPathComponent("syn-dvr-ads-\(UUID().uuidString)", isDirectory: true)
    try fm.createDirectory(at: work, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: work) }

    let config = work.appendingPathComponent("comskip.ini")
    try "output_default=0\noutput_edl=1\nverbose=0\n".write(to: config, atomically: true, encoding: .utf8)
    _ = try processRun(comskip, ["--ini=\(config.path)", "--output=\(work.path)", original.path], timeout: 14400)
    let edls = try fm.contentsOfDirectory(at: work, includingPropertiesForKeys: nil)
        .filter { $0.pathExtension.lowercased() == "edl" }.sorted { $0.path < $1.path }
    guard let edl = edls.first else { return ("NONE", "Comskip no detectó pausas comerciales.") }
    let cuts = try readCuts(edl, total: total)
    if cuts.isEmpty { return ("NONE", "No se detectaron cortes publicitarios fiables.") }
    let kept = keepParts(cuts, total: total)
    let preserved = kept.reduce(0.0) { $0 + $1.length }
    let removedFraction = (total - preserved) / total
    guard !kept.isEmpty, preserved >= 60, removedFraction <= 0.55, kept.count <= 80 else {
        throw ProcessingFailure("Detección dudosa; se ha cancelado para proteger el contenido.")
    }

    var segments: [URL] = []
    for (index, part) in kept.enumerated() {
        let segment = work.appendingPathComponent(String(format: "segment-%03d.mkv", index))
        _ = try processRun(ffmpeg, ["-hide_banner", "-loglevel", "error", "-nostdin",
                                    "-i", original.path, "-ss", String(format:"%.3f", part.start),
                                    "-t", String(format:"%.3f", part.length), "-map", "0", "-c", "copy",
                                    "-avoid_negative_ts", "make_zero", "-y", segment.path])
        guard (try? fm.attributesOfItem(atPath: segment.path)[.size] as? NSNumber)?.int64Value ?? 0 > 0 else {
            throw ProcessingFailure("FFmpeg no pudo generar el tramo \(index).")
        }
        segments.append(segment)
    }
    let concat = work.appendingPathComponent("unir.txt")
    let contents = segments.map { "file '\($0.path)'\n" }.joined()
    try contents.write(to: concat, atomically: true, encoding: .utf8)
    // Temporal en la carpeta del vídeo, para moverlo sin recodificar ni reemplazar el original.
    let provisional = original.deletingLastPathComponent().appendingPathComponent(".syn-dvr-\(UUID().uuidString).mkv")
    defer { try? fm.removeItem(at: provisional) }
    _ = try processRun(ffmpeg, ["-hide_banner", "-loglevel", "error", "-nostdin", "-f", "concat",
                                "-safe", "0", "-i", concat.path, "-map", "0", "-c", "copy", "-y", provisional.path])
    guard (try? fm.attributesOfItem(atPath: provisional.path)[.size] as? NSNumber)?.int64Value ?? 0 > 0 else {
        throw ProcessingFailure("FFmpeg no ha podido unir los segmentos.")
    }
    let actual = try duration(provisional, ffprobe)
    guard abs(actual - preserved) <= max(12.0, preserved * 0.08) else {
        throw ProcessingFailure("La duración del montaje no es coherente con los cortes. Copia descartada.")
    }
    // NSFileManager.moveItem falla si el destino existe, nunca sobrescribe un archivo.
    let result = try outputPath(original)
    try fm.moveItem(at: provisional, to: result)
    return ("OK", result.path)
}

let args = CommandLine.arguments
if args.count != 5 {
    print("ERROR|Argumentos incorrectos del procesador de anuncios.")
    exit(2)
}
do {
    let result = try cleanAds(URL(fileURLWithPath: args[1]), comskip: args[2], ffmpeg: args[3], ffprobe: args[4])
    print("\(result.0)|\(result.1)")
    exit(0)
} catch {
    let message = String(String(describing: error).replacingOccurrences(of: "\n", with: " ").prefix(350))
    print("ERROR|\(message)")
    exit(1)
}
