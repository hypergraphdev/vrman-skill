# Script JSON format (vrman-script v1)

Write an authored `vrman-script` and import it into the theatre, or call `compile_performance`. The studio compiles it into a replayable record and performs each segment in order. The repository example is `data/world/scripts/wusong-tavern.json`.

Narrative descriptions, titles, character names and dialogue can be English. Keep API keys, asset IDs and enumerated values exactly as documented. In particular, era, seating-style and delivery values below are Chinese engine identifiers, not prose to translate.

## 1. Two JSON formats

| `kind` | Author | Contents | Use |
|---|---|---|---|
| `vrman-script` | A person or AI | Scene descriptions, named landmarks, furniture and actions | Compile, then perform |
| `vrman-theater` | The studio compiler | Resolved coordinates, timing and engine steps | Replay or export; editable source records can also be downloaded |

Author `vrman-script`. Compiler errors identify the affected segment, step and field. The compiler resolves scenery and costumes, converts landmarks into coordinates, inserts necessary movement and handling, and validates the resulting performance.

## 2. Minimal example

```json
{
 "kind": "vrman-script", "version": 1, "title": "The roadside inn", "era": "宋",
 "cast": [
  {"id": "guest", "name": "Guest", "sex": "male", "age": "adult", "tag": "travelling merchant", "voice": "en-US-GuyNeural"},
  {"id": "host", "name": "Innkeeper", "sex": "male", "age": "elder", "voice": "en-US-GuyNeural", "costume": {"hair_color": "银灰"}}
 ],
 "places": [
  {"id": "inn", "name": "Roadside inn", "scene": {
    "look": "A village inn at dusk, with a square table, two benches and a tall counter against the back wall",
    "kind": "indoor", "ground": "wood",
    "seating": {"style": "对坐", "table": "g-furniture-square-table", "seat": "g-furniture-long-bench", "name": "table"},
    "things": [
     {"name": "counter", "id": "g-furniture-song-table", "what": "counter", "where": "back"},
     {"name": "bowl", "id": "g-wuxia-wine-bowl", "what": "wine bowl", "on": "counter"},
     {"name": "jug", "id": "a-story-v1-wine-jug", "what": "wine jug", "on": "counter"}
    ]}}
 ],
 "segments": [
  {"place": "inn", "summary": "A guest sits down and the innkeeper serves a bowl of wine.",
   "cast": [{"id": "guest", "position": "front"}, {"id": "host", "position": "counter.front"}],
   "steps": [
    {"action": "enter", "actor": "guest", "from": "front"},
    {"action": "sit", "actor": "guest", "seat": "table-right"},
    {"action": "say", "actor": "guest", "to": "host", "text": "A bowl of wine, please!", "delivery": "大喊"},
    {"action": "grasp", "actor": "host", "entity": "bowl"},
    {"action": "release", "actor": "host", "entity": "bowl", "onto": "table", "for": "guest"},
    {"action": "grasp", "actor": "host", "entity": "jug"},
    {"action": "parallel", "actions": [
     {"action": "hold", "actor": "host", "entity": "jug", "to": "over:bowl", "duration": 1.4},
     {"action": "animate", "entity": "bowl", "clip": "fill-empty", "duration": 1.4}]},
    {"action": "grasp", "actor": "guest", "entity": "bowl"},
    {"action": "hold", "actor": "guest", "entity": "bowl", "to": [-0.1, 1.22, 0.18], "duration": 1.5},
    {"action": "release", "actor": "guest", "entity": "bowl"}
   ]}
 ]
}
```

Step `id` and `next` may be omitted. The compiler numbers and connects the steps and adds a final `cut`.

## 3. Top-level fields

All fields below are required.

| Field | Value |
|---|---|
| `kind` | `"vrman-script"` |
| `version` | `1` |
| `title` | Performance title |
| `era` | One of `先秦`, `秦汉`, `魏晋`, `隋唐`, `宋`, `元`, `明`, `清`, `现代`, `奇幻`; selects the costume/prop era |
| `cast` | Up to 12 characters; at most 4 on stage at once |
| `places` | Locations and scene descriptions from which the studio builds sets |
| `segments` | Between 1 and 30 performance segments |

Era meanings, in order: pre-Qin; Qin/Han; Wei/Jin; Sui/Tang; Song; Yuan; Ming; Qing; modern; fantasy. Send the Chinese value, for example `"era":"宋"` for the Song dynasty.

## 4. Characters: `cast[]`

| Field | Meaning |
|---|---|
| `id` | Short identifier beginning with a letter, up to 32 characters; used in steps |
| `name` | Display name for subtitles |
| `sex` | `male` or `female` |
| `age` | `child`, `adult` or `elder` |
| `tag`, `rank` | Identity and social rank; historical casting uses them with the era to select clothes and headwear |
| `looks` | Appearance description for readers |
| `voice` | Voice ID from `list_voices` or `data/world/voices.json`; match the dialogue language |
| `rate`, `pitch` | Speech rate from -30 to 30, pitch from -20 to 20 |
| `costume` | Appearance settings below |

Costume settings:

- Historical adults and elders receive clothes and headwear based on era and identity. Override `hair_color`, `skin`, `beard` (tags such as `goatee`, `short_full`, or `none`), and `headwear:"none"` when appropriate.
- Hair palette values: `黑色` (black), `深棕` (dark brown), `棕色` (brown), `栗色` (chestnut), `金色` (blond), `亚麻` (flaxen), `红棕` (auburn), `银灰` (silver grey).
- Skin palette values: `瓷白`, `象牙`, `自然`, `小麦`, `蜜色`, `古铜`, `棕褐`, `深棕`. Use the exact names returned by the palette tools.
- Modern adults use tags for `hair`, `outfit`, `shirt`, `beard`, `glasses`, `headwear` and `eyebrow`, for example `"outfit":"formal business suit"`. Use `none` to omit a part.
- Children use a child character ID in `preset`.

Missing costume matches are reported in `gaps`. A performance can still compile; inspect and explain those gaps rather than claiming an exact visual match.

## 5. Locations: `places[]`

Each location is `{id, name, scene}`. The studio assembles `scene` from library props and keeps space clear for acting.

| Scene field | Meaning |
|---|---|
| `look` | Scene description, up to 120 characters |
| `kind` | `indoor` (walls with an open front facing the audience) or `outdoor` |
| `ground` | `wood`, `stone`, `paving`, `dirt`, `grass`, `sand`, `snow` |
| `sky` | `clear`, `overcast`, `dawn`, `dusk`, `night` for outdoor scenes |
| `weather` | `none`, `snow`, `rain`, `fog` |
| `walls`, `floor` | Indoor surface colors such as `"#cdbb98"` |
| `seating` | Table and seats, described below |
| `things` | Up to 6 kinds of additional objects, at most 6 instances each |

`seating.style` accepts `对坐` (opposite seats), `主客` (a host behind the table and guests on either side), or `围坐` (surrounding seats). `table` and `seat` are asset IDs. `name` names the table, default `table`; generated seats are named `table-left`, `table-right` and `table-behind` as applicable.

| `things[]` field | Meaning |
|---|---|
| `what` | Object label; used for library lookup when `id` is absent. Prefer a returned asset ID for reliable selection |
| `id` | Exact prop ID from the current library |
| `name` | Short instance name. Furniture names become landmarks such as `counter.front`; small items use the name as their performance entity ID. Multiple instances receive `-1`, `-2` suffixes |
| `count` | Number of instances, default 1 |
| `where` | `back`, `left`, `right`, `around`, `far` |
| `on` | Name of supporting furniture; items placed on furniture can be picked up during the performance |
| `color` | Instance color override |

Standing actors need a reachable surface at least 0.65 m high. Use a high table for a counter, such as `g-furniture-song-table` (0.8 m). Low tables are reachable by seated actors. Large jars and chests belong on the ground without `on`. If a surface is full, the compiler relocates small items to another surface, or to the ground as a last resort, and records this in `notes`.

## 6. Segments: `segments[]`

| Field | Meaning |
|---|---|
| `place` | Location ID from `places` |
| `summary` | One-sentence description for readers and continuity |
| `cast` | Present actors with `id`, opening `position`, optional `face` target and starting `seat`. Consecutive segments in the same place retain previous positions and seated state |
| `entities` | Newly introduced props with `id`, asset ID in `asset`, furniture in `on`, landmark in `position`, initial carrier in `with`, `wield:true` for a held weapon, or key entity ID in `lock`. Do not duplicate small items already placed with `scene.things[].on` |
| `steps` | Actions below |

The item ledger preserves object positions, seated actors and held items across consecutive segments in the same location.

## 7. Actions and landmarks

Use landmarks for stage positions:

- `center`, `left`, `right`, `far-left`, `far-right`, `front`, `front-left`, `front-right`, `back`, `back-left`, `back-right`.
- Furniture names, such as `counter` (its front) or `counter.front`, `counter.back`, `counter.left`, `counter.right`.
- Nearby people or objects, such as `near:guest` or `near:guest.left`.

Every step has an `action`. The table lists its other fields; optional fields may be omitted when their default behavior is appropriate.

| Action | Fields | Behavior |
|---|---|---|
| `say` | `actor`, `to`, `text`, `delivery`, `emotion`, `motion` | Dialogue with an optional gesture motion ID. Delivery values are listed below |
| `act` | `actor`, `motion`, `duration`, `face` | Play a library motion. A standing motion first makes a seated actor stand |
| `enter` | `actor`, `from` | Enter from `left`, `right`, `back` or `front` and walk to the cast position; `front` is the audience-side entrance |
| `exit` | `actor`, `to` | Leave through one of the same four sides |
| `move` | `actor`, `to`, `run` | Walk or run to a landmark; duration follows distance |
| `sit` | `actor`, `seat` | Walk to furniture and take an available seat |
| `stand` | `actor` | Stand up |
| `kneel` | `actor`, `face`, `bow` | Approach the target and kneel in front; `bow` is 0–3 |
| `grasp` | `actor`, `entity` | Approach and pick up a small object (up to 0.4 m diameter), bending for floor objects; weapons and long handled objects use a grip |
| `hold` | `actor`, `entity`, `to`, `duration` | Hold at actor-relative `[x,y,z]` or `"over:entityId"`; see below |
| `release` | `actor`, `entity`, `onto`, `for`, `give` | Place on a surface or hand to another actor; see below |
| `stow` | `actor`, `entity` | Carry the item on the actor's body |
| `wield` | `actor`, `entity` | Draw a carried weapon into the hand |
| `animate` | `entity`, `clip`, `duration`, `actor` | Object animation: `fill-empty` for bowls/jars, `open`/`close` for doors/chests. With `actor`, the actor walks over to operate it |
| `fight` | `actors`, `weapons`, `rounds`, `winner`, `ending` | Choreograph a fight with sound. `actors` is a pair; `weapons` maps actor IDs to weapon IDs; `rounds` is 2–12; `ending` is `kneel`, `fall`, `none` or `flee`. Human/animal fights use the animal entity ID as the second participant |
| `shoot` | `actor`, `at`, `bow`, `ending` | Archery sequence; `ending` is `fall`, `hit` or `miss` |
| `mount` / `dismount` | `actor`, plus horse `entity` for `mount` | Mount or dismount a horse |
| `hug` | `actor`, `with`, `duration` | Embrace another actor |
| `transform` | `actor`, `into` | Transform into another character or depart in smoke |
| `sound` | `sound`, `volume` | Play a sound ID from the library |
| `wait` | `duration` | Pause |
| `parallel` | `actions` | Up to 6 concurrent actions. Only one speaker at a time, and one action per actor at a time |

`delivery` values: `平静` calm, `温柔` gentle, `高兴` happy, `兴奋` excited, `得意` pleased, `大笑` laughing, `惊讶` surprised, `害怕` frightened, `急切` urgent, `生气` angry, `大喊` shouting, `冷淡` cold, `难过` sad, `疲惫` tired, `低语` whispering, `严肃` serious. Send the Chinese value even for English dialogue.

`hold.to` coordinates are relative to the actor: approximately `[-0.22,1.05,0.25]` at the chest, `[-0.1,1.22,0.18]` at the mouth while seated, or `[-0.12,1.5,0.2]` while standing. `over:bowl` positions the held item over a bowl for pouring; the compiler handles approach and facing.

`release.onto` names furniture or another entity. Combine it with `for:actorId` to serve into free space within the guest's reach. `give:actorId` transfers directly into someone's hand. Without an explicit target, a seated actor puts the item back on the table, preserving its original spot when possible; a standing actor uses a nearby table or hands it to a nearby person if no table is available.

## 8. Compiler assistance

The compiler resolves landmarks and walking durations; approaches reachable sides of furniture before grasping; moves inaccessible tabletop objects toward a free edge; separates served dishes; returns bowls to their original places; removes incompatible full-body actions and gestures while carrying; seats standing actors before seated motions; stows small held items or returns cups/bowls at segment boundaries; and sets speech rate, pitch and expression from delivery. Mixed Chinese/English lines use a Chinese voice.

Review `notes` for adjustments and `gaps` for missing assets. These checks support staging; inspect the resulting performance rather than assuming every creative choice is correct.

## 9. Everyday staging rules

- Guests enter, sit and eat or drink. The host physically serves with `release` + `onto` + `for`. Pour using `hold` over the bowl alongside `animate` with `fill-empty`. Do not make the guest fetch their own meal or put a served bowl directly into their hand.
- Food, drinks, bowls, cups and books belong on a surface, not the floor.
- Promised actions must happen: a request to bring wine should be followed by carrying and serving it; refilling should visibly pour.
- Use seated gestures for seated speakers.
- An actor who left the room stays absent until an `enter` action brings them back.

## 10. Replayable records: `vrman-theater`

The compiler returns a record with `kind:"vrman-theater"`, `title`, `era`, `story`, `segments`, `notes` and `gaps`. `story.cast` contains assembled appearances; `story.places` contains resolved sets. Each segment includes an engine `program` (version 2), `place`, source `steps` and dialogue `lines` with `who` and `words`.

The engine validator is `world_contract.validate_v2`. Usually edit the authored script and recompile instead of editing low-level engine coordinates. Save the record for replay and use `render_performance_video` for MP4 export; JSON itself is not a video.

## 11. Example authoring request

> Write a vrman-script JSON using this specification.
> Story: [the user's premise]
>
> Use IDs returned by asset, motion, sound and voice search. Describe sets; use `seating` for tables and seats, and named `on` items for objects actors will handle. Use reachable counters at least 0.65 m high. Express stage positions as landmarks, except actor-relative `hold` positions. Follow the serving and continuity rules above. Aim for 10–40 steps per segment with at most 4 actors on stage. Preserve the requested narration and dialogue languages. Return JSON.
