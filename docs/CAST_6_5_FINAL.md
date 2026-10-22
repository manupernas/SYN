# SYN Cast 6.5 — verified integration for SYN 1.3.3

This repository incorporates the locally user-verified Cast Beta 6.5 on Fedora ARM64 in a VM.

- One provider connection and one HLS relay shared by SYN and Chromecast when both show the same channel.
- Local channel changes during Chromecast playback subject to the selected connection limit and DVR reservations.
- Rejoining the Cast channel reuses the existing HLS segments, without a duplicate IPTV session.
- Stopping Chromecast restores local playback; DVR remains supported.
- Mandarin-orange Chromecast icon remains visible in light and dark themes.
- The in-app Chromecast slider offers **720p** and **1080p** only. 720p is the recommended starting setting, since 1080p transcoding did not run reliably inside the tested virtual machine. Changes apply to the next Cast session.
- H.264/AAC transcoding parameters for the 720p setting are retained. 1080p is optional and demands greater CPU capacity.
- Some brief startup buffering was observed, and recovered. This does not guarantee stability on other devices.

Cast requires a separate host-side Python service, host FFmpeg with libx264/AAC and PyChromecast; consult `docs/RELEASE_1.3.3.md` and `instalar-servicio-cast.sh`. Building a Flatpak alone does **not** install this external host service.

No IPTV playlists, provider URLs, subscriptions, credentials, tokens, user DVR data or video files are bundled.
