import AppKit
import SwiftUI

@main
@MainActor
struct SYNDVRMenuApp: App {
    @StateObject private var dvr = SYNDVRMenuModel()

    var body: some Scene {
        MenuBarExtra {
            DVRPopover(dvr: dvr)
        } label: {
            if dvr.isRecording {
                Image(systemName: "record.circle.fill")
                    .foregroundStyle(.red)
                    .help("SYN DVR · \(dvr.active.count) grabación(es)")
            } else if dvr.isReconnecting {
                Image(systemName: "arrow.clockwise.circle.fill")
                    .foregroundStyle(.orange)
                    .help("SYN DVR · Reconectando")
            } else if !dvr.workerOnline {
                Image(systemName: "record.circle")
                    .help("SYN DVR · Servicio no disponible")
            } else {
                Image(systemName: "record.circle")
                    .help("SYN DVR · Preparado")
            }
        }
        .menuBarExtraStyle(.window)
    }
}

private struct DVRPopover: View {
    @ObservedObject var dvr: SYNDVRMenuModel
    // SYN_POOL_MENU_31: configurable subscription limit, persisted for the engine.
    @State private var connections = 1
    private var configURL: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/SYN DVR Engine 2.0/config.json")
    }
    private func loadConnections() {
        guard let data = try? Data(contentsOf: configURL),
              let dict = try? JSONSerialization.jsonObject(with:data) as? [String: Any],
              let num = dict["maxConnections"] as? Int, (1...8).contains(num) else { return }
        connections = num
    }
    private func saveConnections(_ count: Int) {
        guard (1...8).contains(count),
              let data = try? JSONSerialization.data(withJSONObject:["maxConnections":count]) else { return }
        do {
            try data.write(to:configURL, options:.atomic)
            try FileManager.default.setAttributes([.posixPermissions: NSNumber(value: 0o600)],
                                                  ofItemAtPath:configURL.path)
        } catch { dvr.message = "No se pudo guardar el límite de conexiones." }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(spacing: 9) {
                Image(systemName: "record.circle.fill")
                    .font(.system(size: 21))
                    .foregroundStyle(dvr.isRecording ? Color.red : Color.accentColor)
                Text("SYN DVR")
                    .font(.system(size: 19, weight: .semibold))
                Spacer()
                HStack(spacing: 5) {
                    Circle()
                        .fill(dvr.workerOnline ? .green : .orange)
                        .frame(width: 7, height: 7)
                    Text(dvr.workerOnline ? "Motor activo" : "Motor desconectado")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(.secondary)
                }
            }
            HStack(spacing: 9) {
                Text("Conexiones IPTV").font(.system(size: 12))
                Spacer()
                Picker("Máximo", selection:$connections) {
                    ForEach(1...8, id: \.self) { n in Text("\(n)").tag(n) }
                }
                .labelsHidden()
                .frame(width: 68)
                .onChange(of: connections) { _, value in saveConnections(value) }
            }
            .onAppear { loadConnections() }
            Divider()
            if !dvr.workerOnline {
                Label("El servicio DVR no está respondiendo. Las programaciones se conservan.",
                      systemImage: "exclamationmark.triangle")
                    .font(.system(size: 12))
                    .foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    sectionTitle("GRABANDO AHORA", image: "record.circle.fill", count: dvr.active.count)
                    if dvr.active.isEmpty {
                        emptyRow("No hay grabaciones activas")
                    } else {
                        ForEach(dvr.active) { job in
                            activeCard(job)
                        }
                    }
                    sectionTitle("PRÓXIMAS GRABACIONES", image: "calendar.clock", count: dvr.upcoming.count)
                    if dvr.upcoming.isEmpty {
                        emptyRow("No hay grabaciones programadas")
                    } else {
                        ForEach(dvr.upcoming.prefix(6)) { job in
                            upcomingRow(job)
                        }
                    }
                    if !dvr.recent.isEmpty {
                        sectionTitle("RECIENTES", image: "clock.arrow.circlepath", count: dvr.recent.count)
                        ForEach(dvr.recent.prefix(5)) { job in
                            recentRow(job)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 365)
            Divider()
            if !dvr.message.isEmpty {
                Text(dvr.message)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 8) {
                Button {
                    dvr.openRecordings()
                } label: {
                    Label("Grabaciones", systemImage: "folder")
                }
                Button {
                    dvr.openSYN()
                } label: {
                    Label("Abrir SYN", systemImage: "play.rectangle")
                }
                Spacer()
                Button {
                    dvr.refresh()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Actualizar estado")
                Button {
                    NSApp.terminate(nil)
                } label: {
                    Image(systemName: "power")
                }
                .help("Salir del controlador; el motor seguirá funcionando")
            }
            .controlSize(.small)
            .buttonStyle(.bordered)
        }
        .padding(16)
        .frame(width: 388)
    }

    private func sectionTitle(_ text: String, image: String, count: Int) -> some View {
        HStack(spacing: 6) {
            Image(systemName: image)
                .foregroundStyle(text == "GRABANDO AHORA" ? Color.red : Color.secondary)
            Text(text)
                .font(.system(size: 11, weight: .bold))
                .tracking(0.6)
            Spacer()
            Text("\(count)")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.tertiary)
        }
    }

    private func emptyRow(_ message: String) -> some View {
        Text(message)
            .font(.system(size: 12))
            .foregroundStyle(.tertiary)
            .padding(.vertical, 6)
    }

    private func activeCard(_ job: MenuDVRJob) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(job.channel)
                        .font(.system(size: 13, weight: .semibold))
                    Text(job.title)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer()
                Text(job.state == "stopping" ? "DETENIENDO" : (job.state == "reconnecting" ? "RECONECTANDO" : "REC ●"))
                    .font(.system(size: 10, weight: .bold, design: .rounded))
                    .foregroundStyle(.red)
            }
            ProgressView(value: job.progress)
                .tint(.red)
            HStack {
                Text("Final previsto: \(job.end.formatted(date: .omitted, time: .shortened))")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Spacer()
                Text(job.remaining)
                    .font(.system(size: 11).monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 6) {
                Button("Mostrar archivo") { dvr.showFile(job) }
                Spacer()
                if job.state != "stopping" {
                    Button("Detener") { dvr.cancel(job) }
                        .tint(.red)
                }
            }
            .controlSize(.small)
        }
        .padding(12)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
    }

    private func upcomingRow(_ job: MenuDVRJob) -> some View {
        HStack(spacing: 8) {
            Image(systemName: job.state == "retrying" ? "arrow.clockwise" : "calendar.badge.clock")
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(job.title).font(.system(size: 12, weight: .medium)).lineLimit(1)
                Text("\(job.channel) · \(job.start.formatted(date: .abbreviated, time: .shortened))")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                dvr.cancel(job)
            } label: {
                Image(systemName: "xmark.circle")
            }
            .buttonStyle(.plain)
            .help("Cancelar programación")
        }
        .padding(.vertical, 3)
    }

    private func recentRow(_ job: MenuDVRJob) -> some View {
        HStack(spacing: 8) {
            Image(systemName: job.state == "finished" ? "checkmark.circle.fill" :
                  job.state == "failed" ? "exclamationmark.triangle.fill" : "minus.circle")
                .foregroundStyle(job.state == "finished" ? Color.green : Color.orange)
            VStack(alignment: .leading, spacing: 2) {
                Text(job.title).font(.system(size: 12, weight: .medium)).lineLimit(1)
                Text(job.statusLabel + (job.error.map { " · " + $0 } ?? ""))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer()
            if ["failed", "cancelled", "expired", "partial"].contains(job.state) {
                Button { dvr.delete(job) } label: {
                    Image(systemName: "trash")
                }
                .buttonStyle(.plain)
                .help("Eliminar tarea sin borrar vídeo")
            }
            if job.outputPath != nil {
                Button { dvr.showFile(job) } label: {
                    Image(systemName: "folder")
                }
                .buttonStyle(.plain)
                .help("Mostrar archivo")
            }
        }
        .padding(.vertical, 3)
    }
}
