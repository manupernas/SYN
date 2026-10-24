import AppKit
import AVKit
import AVFoundation

// SYN-Mac: independent native AVPlayer with Apple's AirPlay route picker.
// No screen mirroring, no third-party casting protocol.
final class SYNAirPlayApp: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var player: AVPlayer!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let arguments = CommandLine.arguments
        guard arguments.count >= 2, let url = URL(string: arguments[1]),
              (url.scheme == "https" || url.scheme == "http") else {
            let alert = NSAlert()
            alert.messageText = "URL no compatible con AirPlay"
            alert.informativeText = "Se necesita un enlace http(s), preferiblemente HLS (.m3u8)."
            alert.runModal()
            NSApp.terminate(nil)
            return
        }
        let channel = arguments.count >= 3 ? arguments[2] : "SYN en directo"
        window = NSWindow(contentRect: NSRect(x:0,y:0,width:680,height:480),
                          styleMask:[.titled,.closable,.miniaturizable,.resizable],
                          backing:.buffered, defer:false)
        window.title = "SYN · AirPlay · " + channel
        window.center()
        window.minSize = NSSize(width:480,height:330)

        let content = NSView(frame: window.contentView!.bounds)
        content.autoresizingMask = [.width,.height]
        window.contentView = content

        let item = AVPlayerItem(url:url)
        player = AVPlayer(playerItem:item)
        player.allowsExternalPlayback = true

        let video = AVPlayerView(frame: NSRect(x:12,y:64,width:656,height:400))
        video.autoresizingMask = [.width,.height]
        video.player = player
        video.controlsStyle = .floating
        content.addSubview(video)

        let airplay = AVRoutePickerView(frame:NSRect(x:20,y:14,width:42,height:42))
        airplay.player = player
        // AVRoutePickerView.prioritizesVideoDevices is unavailable on macOS.
        airplay.autoresizingMask = [.maxXMargin,.maxYMargin]
        content.addSubview(airplay)

        let label = NSTextField(labelWithString: "Elige un televisor AirPlay · HLS recomendado · Otros formatos pueden fallar")
        label.frame = NSRect(x:76,y:18,width:580,height:28)
        label.autoresizingMask = [.width,.maxYMargin]
        label.font = NSFont.systemFont(ofSize:12)
        label.textColor = .secondaryLabelColor
        content.addSubview(label)

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps:true)
        player.play()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = SYNAirPlayApp()
app.delegate = delegate
app.run()
