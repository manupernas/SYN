import AppKit
import UserNotifications

final class NotificationApp: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        let args = CommandLine.arguments
        if args.count < 3 { NSApp.terminate(nil); return }
        let center = UNUserNotificationCenter.current()
        let title = String(args[1].prefix(120))
        let body = String(args[2].prefix(550))
        center.requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            let note = UNNotificationRequest(identifier: UUID().uuidString,
                                             content: content, trigger: nil)
            center.add(note) { _ in
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { NSApp.terminate(nil) }
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 10.0) { NSApp.terminate(nil) }
    }
}
let app = NSApplication.shared
let delegate = NotificationApp()
app.delegate = delegate
app.run()
