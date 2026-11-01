import AppKit
import SwiftUI

// SYN_DVR_DASHBOARD_322 — fixed popover content height, no recording engine changes.
@main
@MainActor
struct SYNDVRMenuApp: App {
    @StateObject private var dvr = SYNDVRMenuModel()

    var body: some Scene {
        MenuBarExtra {
            DVRDashboard(dvr:dvr)
        } label: {
            if dvr.isRecording {
                Image(systemName:"record.circle.fill")
                    .foregroundStyle(.red)
                    .help("SYN DVR · \(dvr.active.count) tarea(s) activas")
            } else if dvr.isReconnecting {
                Image(systemName:"arrow.clockwise.circle.fill")
                    .foregroundStyle(.orange)
                    .help("SYN DVR · Recuperando señal")
            } else {
                Image(systemName:"record.circle")
                    .help(dvr.workerOnline ? "SYN DVR · Listo" : "SYN DVR · Motor desconectado")
            }
        }
        .menuBarExtraStyle(.window)
    }
}

private struct DVRDashboard: View {
    @ObservedObject var dvr: SYNDVRMenuModel
    @State private var connections = 1
    @State private var synServerSettingsOpen40 = false

    // NSMenuBarExtra's window cannot reliably infer ScrollView height.
    // A maxHeight alone may collapse the recording list to ZERO points.
    // Give it an explicit height, adapting to the number of jobs.
    private var recordingPanelHeight: CGFloat {
        let activeRows = min(dvr.active.count, 2)
        let scheduledRows = min(dvr.upcoming.count, 4)
        let recentRows = min(dvr.recent.count, 4)
        let wanted = 150 + 188 * activeRows + 48 * scheduledRows
            + (recentRows == 0 ? 0 : 35 + 40 * recentRows)
        return CGFloat(min(440, max(190, wanted)))
    }

    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            HStack(spacing:9) {
                Image(systemName:"record.circle.fill")
                    .font(.system(size:21))
                    .foregroundStyle(dvr.isRecording ? Color.red : Color.secondary)
                VStack(alignment:.leading,spacing:1) {
                    HStack(spacing:6) {
                        Text("SYN DVR").font(.system(size:18,weight:.semibold))
                        Text("v3.2.2").font(.system(size:10,weight:.medium)).foregroundStyle(.secondary)
                    }
                    Text(dvr.workerOnline ? "Motor en funcionamiento" : "Motor no disponible")
                        .font(.system(size:11)).foregroundStyle(.secondary)
                }
                Spacer()
                Circle().fill(dvr.workerOnline ? Color.green : Color.orange).frame(width:8,height:8)
                Text("\(dvr.occupied)/\(dvr.capacity)")
                    .font(.system(size:11,weight:.medium,design:.rounded))
                    .monospacedDigit()
                    .help("Sesiones de recepción ocupadas / contratadas")
            }
            Divider()
            if !dvr.workerOnline {
                Label("El motor no responde. Las tareas siguen guardadas.",systemImage:"exclamationmark.triangle")
                    .font(.system(size:11)).foregroundStyle(.orange)
            }
            ScrollView {
                VStack(alignment:.leading,spacing:14) {
                    heading("GRABANDO / EN CURSO",icon:"record.circle.fill",count:dvr.active.count)
                    if dvr.active.isEmpty { empty("No hay grabaciones activas") }
                    else { ForEach(dvr.active) { job in liveCard(job) } }

                    heading("PROGRAMADAS",icon:"calendar.clock",count:dvr.upcoming.count)
                    if dvr.upcoming.isEmpty { empty("No hay grabaciones pendientes") }
                    else { ForEach(dvr.upcoming.prefix(7)) { job in scheduledRow(job) } }

                    if !dvr.recent.isEmpty {
                        heading("RECIENTES",icon:"clock.arrow.circlepath",count:dvr.recent.count)
                        ForEach(dvr.recent.prefix(6)) { job in recentRow(job) }
                    }
                }
                .frame(maxWidth:.infinity,alignment:.leading)
            }
            .frame(height: recordingPanelHeight)
            Divider()
            HStack(spacing:8) {
                Text("Conexiones IPTV").font(.system(size:12))
                Spacer()
                Picker("Límite",selection:$connections) {
                    ForEach(1...8,id:\.self) { n in Text("\(n)").tag(n) }
                }
                .labelsHidden()
                .frame(width:70)
                .onChange(of:connections) { _,value in
                    if value != dvr.capacity { dvr.saveCapacity(value) }
                }
            }
            if !dvr.message.isEmpty {
                Text(dvr.message).font(.system(size:11))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal:false,vertical:true)
            }
            HStack(spacing:8) {
                Button { dvr.openRecordings() } label: { Label("Archivos",systemImage:"folder") }
                Button { dvr.openSYN() } label: { Label("Abrir SYN",systemImage:"play.rectangle") }
                Button { synServerSettingsOpen40 = true } label: { Label("Servidor",systemImage:"network") }
                Spacer()
                Button { dvr.refresh() } label: { Image(systemName:"arrow.clockwise") }
                    .help("Actualizar")
                Button { NSApp.terminate(nil) } label: { Image(systemName:"xmark.circle") }
                    .help("Cerrar solo el controlador. El DVR seguirá grabando.")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding(15)
        .frame(width:405)
        .onAppear {
            dvr.refresh()
            connections = dvr.capacity
        }
        .sheet(isPresented:$synServerSettingsOpen40) { SYNRemoteServerSettings40() }
    }

    private func heading(_ value:String,icon:String,count:Int) -> some View {
        HStack(spacing:6) {
            Image(systemName:icon).foregroundStyle(value.contains("CURSO") ? Color.red : Color.secondary)
            Text(value).font(.system(size:11,weight:.bold)).tracking(0.45)
            Spacer()
            Text("\(count)").font(.caption.monospacedDigit()).foregroundStyle(.tertiary)
        }
    }
    private func empty(_ value:String) -> some View {
        Text(value).font(.system(size:12)).foregroundStyle(.tertiary).padding(.vertical,5)
    }
    private func liveCard(_ job:MenuDVRJob) -> some View {
        VStack(alignment:.leading,spacing:9) {
            HStack(alignment:.top) {
                VStack(alignment:.leading,spacing:3) {
                    Text(job.channel).font(.system(size:13,weight:.semibold))
                    Text(job.title).font(.system(size:12)).foregroundStyle(.secondary).lineLimit(2)
                }
                Spacer()
                Text(job.state == "recording" ? "● REC" : job.statusLabel.uppercased())
                    .font(.system(size:10,weight:.bold,design:.rounded))
                    .foregroundStyle(job.state == "recording" ? Color.red : Color.orange)
                    .lineLimit(1)
            }
            ProgressView(value:job.progress).tint(.red)
            HStack {
                Label(job.statusLabel, systemImage:job.state == "recording" ? "waveform" : "arrow.clockwise")
                    .foregroundStyle(job.state == "recording" ? Color.primary : Color.orange)
                Spacer()
                Text(job.received).monospacedDigit()
            }
            .font(.system(size:11))
            HStack {
                VStack(alignment:.leading,spacing:2) {
                    Text("Transcurrido desde inicio").foregroundStyle(.secondary)
                    Text(job.elapsed).monospacedDigit()
                }
                Spacer()
                VStack(alignment:.trailing,spacing:2) {
                    Text("Restante previsto").foregroundStyle(.secondary)
                    Text(job.remaining).monospacedDigit()
                }
            }
            .font(.system(size:11))
            if let retry = job.retryAt, ["retrying", "reconnecting", "waiting_for_tuner"].contains(job.state) {
                Text("Siguiente intento: \(retry.formatted(date:.omitted,time:.standard))")
                    .font(.system(size:10)).foregroundStyle(.secondary)
            }
            HStack {
                Button("Mostrar archivo") { dvr.showFile(job) }
                Spacer()
                if job.canCancel {
                    Button("Detener grabación") { dvr.cancel(job) }.tint(.red)
                } else if job.state == "stopping" || job.cancellationRequested {
                    Text("Deteniendo…").foregroundStyle(.secondary)
                }
            }
            .controlSize(.small)
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius:11).fill(Color(nsColor:.controlBackgroundColor)))
    }
    private func scheduledRow(_ job:MenuDVRJob) -> some View {
        HStack(spacing:8) {
            Image(systemName:"calendar.badge.clock").foregroundStyle(.secondary)
            VStack(alignment:.leading,spacing:2) {
                Text(job.title).font(.system(size:12,weight:.medium)).lineLimit(1)
                Text("\(job.channel) · \(job.start.formatted(date:.abbreviated,time:.shortened))")
                    .font(.system(size:11)).foregroundStyle(.secondary)
            }
            Spacer()
            if job.canCancel {
                Button { dvr.cancel(job) } label: { Image(systemName:"xmark.circle") }
                    .buttonStyle(.plain).help("Cancelar programación")
            } else if job.cancellationRequested {
                Image(systemName:"hourglass").foregroundStyle(.secondary)
            }
        }.padding(.vertical,3)
    }
    private func recentRow(_ job:MenuDVRJob) -> some View {
        HStack(spacing:8) {
            Image(systemName:job.state == "finished" ? "checkmark.circle.fill" : "exclamationmark.circle")
                .foregroundStyle(job.state == "finished" ? Color.green : Color.orange)
            VStack(alignment:.leading,spacing:2) {
                Text(job.title).font(.system(size:12,weight:.medium)).lineLimit(1)
                Text("\(job.statusLabel) · \(job.received)")
                    .font(.system(size:11)).foregroundStyle(.secondary)
            }
            Spacer()
            if job.canDelete {
                Button { dvr.delete(job) } label: { Image(systemName:"trash") }
                    .buttonStyle(.plain).help("Eliminar tarea, conservar vídeo")
            }
            Button("Ver en SYN") { dvr.verEnSYN93(job) }
                .font(.system(size: 11, weight: .medium))
                .help("Abrir grabación en VLC dentro de SYN")
            Button { dvr.showFile(job) } label: { Image(systemName:"folder") }
                .buttonStyle(.plain).help("Mostrar archivo")
        }.padding(.vertical,3)
    }
}

// SYN_DVR_REMOTE_SETTINGS_40 · only configures the HTTPS gateway, never FFmpeg.
private struct SYNRemoteServerSettings40: View {
    @Environment(\.dismiss) private var dismiss
    @State private var port = "8090"
    @State private var lanEnabled = true
    @State private var folder = ""
    @State private var password = ""
    @State private var passwordEnabled = false
    @State private var alreadyHasPassword = false
    @State private var information = ""
    @State private var message = ""
    @State private var busy = false
    @State private var serverActive = false
    @State private var diskText = "—"
    @State private var ramText = "—"
    @State private var pressureText = "No disponible"
    @State private var usedConnections = "—"

    private var support: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/SYN DVR Remote")
    }
    private var program: URL { support.appendingPathComponent("syn_dvr_remote.py") }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                Image(systemName:"server.rack").foregroundStyle(.teal)
                Text("SYN DVR · Servidor local").font(.title3.bold())
                Spacer()
                Circle().fill(serverActive ? Color.green : Color.orange).frame(width:9,height:9)
                Text(serverActive ? "Conectado" : "No disponible")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Tu grabador sigue siendo independiente. Configura cómo se conectan otros dispositivos, sin alterar la captura actual.")
                .font(.caption).foregroundStyle(.secondary)
            Divider()
            HStack {
                Text("IP local")
                Spacer()
                Text(localAddress).textSelection(.enabled).monospacedDigit()
                Button { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(localAddress,forType:.string) } label: {
                    Image(systemName:"doc.on.doc")
                }.buttonStyle(.plain).help("Copiar IP")
            }
            HStack {
                Text("Puerto HTTPS")
                Spacer()
                TextField("8090",text:$port).frame(width:88).multilineTextAlignment(.trailing)
            }
            Toggle("Permitir conexiones desde la red local",isOn:$lanEnabled)
            HStack {
                Text("Carpeta de grabaciones")
                Spacer()
                Text(folder.isEmpty ? "Sin configurar" : (folder as NSString).lastPathComponent)
                    .lineLimit(1).foregroundStyle(.secondary)
                Button("Elegir…") { chooseFolder() }
            }
            Toggle("Proteger acceso con contraseña",isOn:$passwordEnabled)
            if passwordEnabled {
                SecureField(alreadyHasPassword ? "Nueva contraseña (en blanco: conservar)" : "Contraseña",text:$password)
                    .textFieldStyle(.roundedBorder)
                Text("Sin longitud mínima. La contraseña nunca se guarda en texto plano.")
                    .font(.system(size:10)).foregroundStyle(.tertiary)
            } else if lanEnabled {
                Text("Atención: sin contraseña, cualquier dispositivo de tu red local podrá consultar y gestionar grabaciones.")
                    .font(.caption).foregroundStyle(.orange)
            }
            Divider()
            Group {
                HStack { Label("Disco disponible",systemImage:"externaldrive"); Spacer(); Text(diskText) }
                HStack { Label("RAM instalada",systemImage:"memorychip"); Spacer(); Text(ramText) }
                HStack { Label("Presión de memoria",systemImage:"waveform.path.ecg"); Spacer(); Text(pressureText) }
                HStack { Label("Conexiones IPTV",systemImage:"antenna.radiowaves.left.and.right"); Spacer(); Text(usedConnections) }
            }.font(.system(size:12))
            if !information.isEmpty {
                Text(information).font(.system(size:10,design:.monospaced))
                    .textSelection(.enabled).foregroundStyle(.secondary)
            }
            if !message.isEmpty { Text(message).font(.caption).foregroundStyle(.secondary) }
            HStack {
                Button("Actualizar estado") { load() }
                Spacer()
                Button("Cerrar") { dismiss() }
                Button("Guardar y aplicar") { save() }.buttonStyle(.borderedProminent).disabled(busy)
            }
        }
        .padding(20)
        .frame(width:480)
        .onAppear { load() }
    }

    private var localAddress: String {
        let output = shell("/sbin/ifconfig",[])
        let pattern = #"inet (\d+\.\d+\.\d+\.\d+)"#
        guard let regex = try? NSRegularExpression(pattern:pattern) else { return "127.0.0.1" }
        let ns=output as NSString
        for match in regex.matches(in:output,range:NSRange(location:0,length:ns.length)) {
            let address=ns.substring(with:match.range(at:1))
            if !address.hasPrefix("127.") && !address.hasPrefix("169.254.") { return address }
        }
        return "127.0.0.1"
    }

    private func shell(_ executable:String,_ arguments:[String]) -> String {
        let p=Process();p.executableURL=URL(fileURLWithPath:executable);p.arguments=arguments
        let out=Pipe();p.standardOutput=out;p.standardError=FileHandle.nullDevice
        do { try p.run() } catch { return "" }
        let data=out.fileHandleForReading.readDataToEndOfFile();p.waitUntilExit()
        return String(data:data,encoding:.utf8) ?? ""
    }

    private func load() {
        let fm=FileManager.default
        let cfg=support.appendingPathComponent("server.json")
        if let data=try? Data(contentsOf:cfg),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any] {
            port=String(json["port"] as? Int ?? 8090)
            folder=json["recordingsFolder"] as? String ?? ""
            lanEnabled=(json["bind"] as? String ?? "127.0.0.1") != "127.0.0.1"
            passwordEnabled=json["authRequired"] as? Bool ?? fm.fileExists(atPath:support.appendingPathComponent("auth.json").path)
            alreadyHasPassword=fm.fileExists(atPath:support.appendingPathComponent("auth.json").path)
        }
        if fm.isExecutableFile(atPath:program.path) {
            information=shell("/usr/bin/python3",[program.path,"info"])
        } else { information="Instala primero SYN DVR Remote 4.1." }
        if let data=try? Data(contentsOf:support.appendingPathComponent("server.heartbeat.json")),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any],
           let stamp=json["timestamp"] as? Double {
            serverActive=abs(Date().timeIntervalSince1970-stamp) < 60
        } else { serverActive=false }
        if !folder.isEmpty,
           let attr=try? fm.attributesOfFileSystem(forPath:folder),
           let free=attr[.systemFreeSize] as? NSNumber {
            diskText=ByteCountFormatter.string(fromByteCount:free.int64Value,countStyle:.file)
        }
        ramText=ByteCountFormatter.string(fromByteCount:Int64(ProcessInfo.processInfo.physicalMemory),countStyle:.memory)
        switch shell("/usr/sbin/sysctl",["-n","kern.memorystatus_vm_pressure_level"]).trimmingCharacters(in:.whitespacesAndNewlines) {
        case "1": pressureText="Normal"
        case "2": pressureText="Moderada"
        case "4": pressureText="Crítica"
        default: pressureText="No disponible"
        }
        let pool=fm.homeDirectoryForCurrentUser.appendingPathComponent(
            "Library/Application Support/SYN DVR Engine 2.0/pool.status.json")
        if let data=try? Data(contentsOf:pool),
           let json=try? JSONSerialization.jsonObject(with:data) as? [String:Any],
           let n=json["occupied"] as? Int, let m=json["maxConnections"] as? Int {
            usedConnections="\(n) / \(m)"
        }
    }

    private func chooseFolder() {
        let panel=NSOpenPanel()
        panel.canChooseDirectories=true;panel.canChooseFiles=false
        panel.allowsMultipleSelection=false;panel.canCreateDirectories=true
        if panel.runModal() == .OK, let url = panel.url { folder = url.path }
    }

    private func save() {
        guard let n=Int(port), (1024...65535).contains(n), !folder.isEmpty else {
            message="Indica un puerto entre 1024 y 65535 y una carpeta válida.";return
        }
        guard !passwordEnabled || !password.isEmpty || alreadyHasPassword else {
            message="Introduce una contraseña o desactiva la protección.";return
        }
        guard FileManager.default.isExecutableFile(atPath:program.path) else {
            message="Primero instala la API SYN DVR Remote.";return
        }
        busy=true
        let payload:[String:Any]=["bind":lanEnabled ? "0.0.0.0" : "127.0.0.1",
                                  "port":n,"recordingsFolder":folder,"password":passwordEnabled ? password : "",
                                  "authRequired":passwordEnabled]
        password=""
        DispatchQueue.global(qos:.userInitiated).async {
            let p=Process();p.executableURL=URL(fileURLWithPath:"/usr/bin/python3")
            p.arguments=[program.path,"configure-stdin"]
            let pipe=Pipe();let result=Pipe()
            p.standardInput=pipe;p.standardOutput=result;p.standardError=result
            var outcome=""
            do {
                let bytes=try JSONSerialization.data(withJSONObject:payload)
                try p.run()
                pipe.fileHandleForWriting.write(bytes)
                try? pipe.fileHandleForWriting.close()
                let data=result.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
                outcome=String(data:data,encoding:.utf8) ?? ""
                if p.terminationStatus==0 {
                    let restart=Process()
                    restart.executableURL=URL(fileURLWithPath:"/bin/launchctl")
                    restart.arguments=["kickstart","-k","gui/\(getuid())/com.mrseivane.syn.dvr.remote"]
                    restart.standardOutput=FileHandle.nullDevice
                    restart.standardError=FileHandle.nullDevice
                    try restart.run();restart.waitUntilExit()
                    if restart.terminationStatus != 0 { outcome += "\nAPI guardada; revisa el servicio." }
                }
            } catch { outcome=error.localizedDescription }
            DispatchQueue.main.async { busy=false;message=outcome;load() }
        }
    }
}
