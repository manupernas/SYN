import SwiftUI

@main
struct SYNNativeApp: App {
    var body: some Scene {
        WindowGroup("SYN") { ContentView() }
            .defaultSize(width: 1300, height: 790)
            .commands {
                CommandGroup(replacing: .newItem) { }
            }
    }
}
