# Koryo TV Kodi Add-on
Kodi add-on for browsing and streaming video content from Koryo TV.

<img width="1707" height="1062" alt="image" src="https://github.com/user-attachments/assets/35afc8e0-fa82-40a0-bbff-114ab010975c" />

## Requirements
- Kodi 19 Matrix or later
- A good internet connection

## Installation
1. Download the latest ZIP file from the [Releases](https://gitea.com/daveesplana/plugin.video.koryotv/releases) section.
2. Open Kodi and select Settings (gear icon).
3. Go to System -> Add-ons.
4. Enable `Unknown sources` if not already enabled.
5. Return to the Add-ons browser and select `Install from zip file`.
6. Choose the downloaded ZIP file and install the add-on.

## Live TV in Kodi PVR (SlyGuy IPTV Merge)
Koryo TV implements the [IPTV Manager](https://github.com/add-ons/service.iptv.manager/wiki/Integration) protocol, which SlyGuy's **IPTV Merge** add-on supports natively as an "add-on source." This lets KCTV, KCBS, and Voice of Korea show up as PVR channels alongside your other IPTV sources, with EPG data pulled in automatically.

1. Install **IPTV Merge** from the SlyGuy Repository (Add-ons -> Install from repository -> SlyGuy Repository -> Program add-ons -> IPTV Merge).
2. Make sure Koryo TV is installed and enabled.
3. In Koryo TV's settings, under **Live TV Integration**, leave "Enable IPTV Manager / IPTV Merge integration" turned on (it's on by default). The EPG URL field is pre-filled with KCTV's guide pointing at [daveesplana/kctv-epg](https://github.com/daveesplana/kctv-epg) — you can change or clear it if you'd rather use your own.
4. Open IPTV Merge -> Add-ons (or "Playlists" -> "Add-on source", depending on version) and select **Koryo TV** as a source.
5. Run "Setup IPTV Simple Client" (or "Sync with IPTV Simple Client") from IPTV Merge's main menu so PVR IPTV Simple Client points at the merged playlist/EPG.
6. Reload add-ons / restart Kodi's PVR manager. KCTV, KCBS, and Voice of Korea should appear as channels (radio channels for KCBS/VOK), with KCTV showing a live programme guide.

Notes:
- KCBS and Voice of Korea are audio-only and are exposed as radio channels.
- Only KCTV has EPG data available from the linked guide; KCBS/VOK will show as channels without programme listings.
- Channels still resolve through Koryo TV's own stream proxy, so server selection (Settings -> Select Server) applies to PVR playback too.


This add-on is an unofficial Kodi plugin and is not endorsed by or affiliated with Koryo Front or any of its content providers.

- The add-on streams content from third-party sources.
- Availability, quality, and legality of streams are not guaranteed.

## License
The source code in this repository is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0).

For full license terms, see the `LICENSE` file included with this repository.
