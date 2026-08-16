# Music — radio stations (`music/` — an `.asset` + `.txt` pair, plus `.ogg` audio)

Music lives in the mod-root `music/` directory — **not** under `common/`. Two text files carry the
data: an **`.asset`** file defines songs (id → `.ogg` file → volume), a **`.txt`** file assigns those
songs to a station with weighted-shuffle rules. The audio itself is Ogg Vorbis files in the same
folder. Vanilla's base station is `music/music.asset` + `music/_songs.txt` with the `.ogg`s beside
them — your mod mirrors that layout.

## Directory & naming rules
| File | Role |
|---|---|
| `music/{key}_music.asset` | song definitions — one `music = { … }` block per track |
| `music/{key}_music.txt` | station header + one assignment block per track |
| `music/*.ogg` | the audio files, same folder the `.asset` points into |

The platform's `music` template writes the `.txt` + `.asset` **pair**; upload each `.ogg` separately
as a raw **binary** file to the same `music/` folder (see entry points below). Net-new filenames —
shadowing vanilla's `_songs.txt` / `music.asset` replaces the base playlist wholesale.

## Song definition (`.asset`)
| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `name` | string ≤ 63 chars | yes | — | song id **and** loc key — `name:0 "Shown Title"` names it in the player |
| `file` | filename incl. `.ogg` | yes | — | the audio file, relative to the `.asset`'s folder |
| `volume` | decimal | no | — | per-track gain without re-encoding (vanilla uses ~0.65) |

## Station assignment (`.txt`)
The file opens with its station, then one block per song:
| Field | Type | Required | Meaning |
|---|---|---|---|
| `music_station` | string | yes | file-level header. `"base_music"` = vanilla's default station; any new id = your own station (GUI required, below) |
| `song` | song id | yes | a `name` from the `.asset` |
| `chance = { … }` | weight block | no | weighted-shuffle weight: `base` (replace) / `add` / `factor` (multiply), plus `modifier = { factor = … <triggers> }` blocks that apply while their triggers hold |

## Custom station = GUI work
Adding songs to `base_music` needs nothing else. A **new** station id only appears in the radio UI if
you also ship:
1. `interface/*.gui` — containers `<station>_faceplate` and `<station>_stations_entry` (copy the
   documented vanilla faceplate skeleton; the names must use your station id as prefix);
2. a 2-frame `.dds` album sprite referenced from `interface/*.gfx` (`noOfFrames = 2` — unselected /
   selected halves);
3. loc — `<station>:0 "Station Name"` plus one `<song name>:0 "Track Title"` line per song.

## Minimal working example (the pair)
`music/{key}_music.asset`:
```
music = {
    name = "mymod_theme"          # id + loc key, max 63 chars
    file = "mymod_theme.ogg"      # upload the .ogg beside this file
    volume = 0.65
}
```
`music/{key}_music.txt`:
```
music_station = "base_music"      # join the default station — no custom GUI needed

music = {
    song = "mymod_theme"
    chance = {
        base = 1
        modifier = {              # twice as likely while at war
            factor = 2
            has_war = yes
        }
    }
}
```

## Platform entry points
- **Template** — MCP `create_raw_from_template(template="music", key="my_radio")` / REST
  `POST /api/projects/{pid}/raw-files/from-template/music` `{key}` → **both** files above
  (key: lowercase `a-z0-9_`, 2–40 chars).
- **Audio** — REST binary upload: `POST /api/projects/{pid}/raw-files/binary` (multipart
  `dest_path` + `file`, ≤ 25 MiB each) with `dest_path` like `music/mymod_theme.ogg`.
- **Any other path** — REST `POST /api/projects/{pid}/raw-files` `{dest_path, content}`.

### Common quirks
- **A wrong `music_station` header fails silently.** Typo the id (or omit the line) and every song in
  that `.txt` simply never plays — no error anywhere. Multiple `.txt` files may feed one station.
- **`.ogg` means real Ogg Vorbis.** A renamed `.mp3`/`.wav` loads as silence or crashes the player —
  re-encode properly; `file =` must include the `.ogg` extension.
- **`chance` only matters in Weighted Shuffle playmode** — direct selection ignores weights. A
  `modifier = { factor = 0 <trigger> }` mutes the song while the trigger holds (vanilla uses this to
  keep war tracks out of peacetime).
- Without a `name:0` loc line the player shows the raw song id.
