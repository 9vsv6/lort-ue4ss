# UE4SS for LORT

This makes [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) (the Unreal Engine scripting and modding loader) work
with **LORT** (Steam app 2956680).

Out of the box, UE4SS crashes LORT on startup. LORT is built on **Unreal Engine 5.7 with Hazelight's AngelScript
fork**, and that fork changes the memory layout of two core engine types. This repo contains the
`MemberVariableLayout.ini` that tells UE4SS the real layout, plus the tools and method used to find it.

## Install
1. Download the **experimental** UE4SS build: `UE4SS_v3.0.1-1152-ge3ba1016.zip` or newer from
   [experimental-latest](https://github.com/UE4SS-RE/RE-UE4SS/releases/tag/experimental-latest). The 2024 stable
   release (v3.0.1) doesn't support UE 5.7.
2. Extract `dwmapi.dll` and the `ue4ss` folder into
   `...\steamapps\common\LORT\bw\Binaries\Win64\` (next to `LortGame-Win64-Shipping.exe`).
3. Copy **`MemberVariableLayout.ini`** from this repo into that `ue4ss` folder:
   `...\LORT\bw\Binaries\Win64\ue4ss\MemberVariableLayout.ini`.
   Alternatively, run `install.ps1` from this repo in PowerShell, which does this step for you:
   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1 -GameDir "D:\SteamLibrary\steamapps\common\LORT"
   ```
4. Launch the game. The log at `ue4ss\UE4SS.log` should show `MemberVariableLayout.ini loaded`,
   `UClass::ClassDefaultObject = 0x170` and `Event loop start`.

**Uninstall:** delete `dwmapi.dll` and the `ue4ss` folder.

Only use mods in single-player or in private co-op with friends who agree to it. LORT has no anti-cheat; don't
take modded clients into public lobbies.

## What's different in LORT, and how it was found

### Problem 1: startup crash ("Locating KismetStringLibrary CDO...")
UE4SS read `UClass::ClassDefaultObject` at the stock 5.x offset `0x110`. In LORT that slot holds part of a TMap,
so UE4SS dereferenced `0x800000004C + 0x18` and crashed.

The AngelScript fork adds a 0x50-byte TMap (reflected function pointers) right after `ClassWithin` (`0xE0`),
shifting every member after it. The same thing happens in Gothic 1 Remake
([RE-UE4SS#1439](https://github.com/UE4SS-RE/RE-UE4SS/issues/1439)), but LORT's offsets differ from Gothic's.

**How the offsets were found:** I parsed UE4SS's crash dump and scanned every `UClass` in it for the 8-byte slot
that points to an object whose `ClassPrivate` is that same class. That slot is the class default object, and
there was exactly one match: `0x170`. The TMaps were then identified by their shape (data pointer, Num/Max,
TBitArray, hash). `FuncMap` has as many entries as the class has functions.

| UClass member | LORT | Stock 5.x |
|---|---|---|
| ClassConfigName | 0x144 | |
| ClassDefaultObject | **0x170** | 0x110 |
| FuncMap | **0x190** | |
| AllFunctionsCache | 0x1E8 | |
| Interfaces | **0x240** | |
| ReferenceSchema | 0x250 | |
| NativeFunctionLookupTable | 0x258 | |

`Interfaces` matters: when it was wrong, calling any function on a class that implements an interface (e.g.
`Pawn:SetActorScale3D`, `UserWidget:IsInViewport`) failed with `Array failed invariants check, ArrayNum exceeds
ArrayMax`. It was confirmed by reading live memory: `Pawn` and `UserWidget` have a 1-element TArray at `+0x240`.

### Problem 2: silent crash on any property read
With UClass fixed, UE4SS started, but reading **any** object property from Lua (e.g. `Engine.GameViewport`)
killed the game instantly. The process died before `UE4SS.log` was flushed, so the log showed nothing.

**Cause:** `FProperty` has 4 extra bytes after `RepIndex` / `BlueprintReplicationCondition`. `Offset_Internal`
is at **`0x48`** (stock `0x44`), and every later member, plus every member of every property subclass, sits
**8 bytes later** than in stock 5.7. `FProperty` is `0x78` bytes instead of `0x70`.

**How it was found:** I read the running game's memory from outside the process with `ReadProcessMemory` (the
`tools/` here) and walked `GameEngine`'s property list (`UStruct::ChildProperties` at `0x50`, `FField::Next` at
`0x18`). The values at `+0x48` increased steadily (`0x12C0`, `0x12C4`, `0x12C8`) and fit within the class's
`PropertiesSize`, so they're the property offsets. The `+0x44` slot is always 0. The subclass members were then
checked one type at a time:

| Member | LORT | Stock 5.7 |
|---|---|---|
| FProperty::Offset_Internal | 0x48 | 0x44 |
| FProperty::PropertyLinkNext | 0x50 | 0x48 |
| FObjectPropertyBase::PropertyClass | 0x78 | 0x70 |
| FStructProperty::Struct | 0x78 | 0x70 |
| FClassProperty::MetaClass | 0x80 | 0x78 |
| FArrayProperty::Inner | 0x80 | 0x78 |
| FBoolProperty::FieldSize | 0x78 | 0x70 |
| FEnumProperty::UnderlyingProp / Enum | 0x78 / 0x80 | 0x70 / 0x78 |

`UObjectBase`, `UStruct`, `FField`, `UFunction` and `FUObjectItem` (0x18, object at +8) are stock.

### Tips for modding LORT
- Gameplay code is AngelScript. Classes live under `/Script/Angelscript.*` (class type `ASClass`), and global
  script functions are UFunctions on `Default__Module_*Statics` objects.
- Stats are GAS attribute sets owned by the character (`BWHealthAttributes`, `BWCombatAttributes`,
  `BWMovementAttributes`, `BWPlayerAttributes`). Change them with `set:TrySetAttributeBaseValue(FName(name), v)`.
- The developers' cheat extensions ship in the game (`BWPlayerCheats`, `BWGameplayCheats`, `BWDebugCheats`,
  `BWAICheats`, `BWChallengeCheats`). Create one with
  `StaticConstructObject(StaticFindObject("/Script/Angelscript.BWPlayerCheats"), pc.CheatManager)` and call
  its functions.
- `AHUD::ReceiveDrawHUD` never fires (the UI is UMG/CommonUI). For on-screen UI, build UMG widgets from Lua.
- If you debug a hard crash, write your Lua log to your own file with `io.open` and close it after every line.
  `UE4SS.log` is lost when the process dies.
- The zDEV build of UE4SS (same commit) puts a symbolized UE4SS call stack into the game's own crash log at
  `%LOCALAPPDATA%\LORT\Saved\Logs\BW.log`.

### Lua gotchas found on LORT
- **Run Lua only on the game thread.** Heavy `LoopAsync` / `ExecuteWithDelay` / `RegisterKeyBind` callbacks
  running at the same time as game-thread Lua corrupted the Lua state. The symptoms were nonsense errors such as
  "UFunction expected 0 parameters, received 1", then an access violation in `lua_setiuservalue`. Use
  `LoopInGameThreadWithDelay` and `ExecuteInGameThreadWithDelay` (both in the experimental build), and read keys
  with `PlayerController:IsInputKeyDown({KeyName = FName("F1")})`.
- **Don't call `UButton:SetStyle(style)`.** Passing an `FButtonStyle` through UE4SS hard-crashes the game. Edit
  `button.WidgetStyle` fields in place before the widget is added to the viewport instead.
- `PlayerController:IsInputKeyDown` is blind while the game's own UI owns input (the main menu, CommonUI
  screens). For keys that must work there, use `RegisterKeyBind` and only queue work with `ExecuteInGameThread`
  from the callback.
- If you switch to `SetInputMode_GameAndUIEx` for a mouse UI, call
  `WidgetBlueprintLibrary:SetFocusToGameViewport()` afterwards. Otherwise the focused widget swallows every key.
- Rounded UMG: set `brush.DrawAs = 4` (RoundedBox) and `brush.OutlineSettings.CornerRadii` in place before the
  widget is added to the viewport. `BackgroundBlur` works for frosted glass.
- `KismetRenderingLibrary:ImportFileAsTexture2D(ctx, absPath)` loads a PNG from disk for `Image:SetBrushFromTexture`.
- `widget:IsHovered()` resolves to a bool value, not the UFunction. Read it defensively, and use
  `Button:IsPressed()` for click detection (a press followed by a release).
- Relative `io.open` paths are relative to `Binaries\Win64`, not the `ue4ss` folder. Use absolute paths, or
  derive the mod folder from `debug.getinfo(1, "S").source`.
- **Saves** are plain JSON (`%LOCALAPPDATA%\LORT\Saved\SaveGames\<SteamID>\ProfileN*.sav`, rotating `_1`/`_2`),
  with no checksum. The game rewrites them from memory while it runs, so edit them only while the game is closed,
  or before the profile loads.

## Tools
`tools/` is read-only: Python 3, Windows, only `PROCESS_VM_READ`. Run each script with the game running and
UE4SS loaded.

| Script | What it does |
|---|---|
| `memread.py` | Minimal process reader plus a UE5 FNamePool decoder |
| `find_names.py` | Finds the FNamePool block array and writes `names_addr.txt` |
| `findobj.py <GUObjectArray> <Name>...` | Finds classes by name via GUObjectArray (address is printed in `UE4SS.log`) |
| `dump_props.py <objectAddress>` | Prints each property type's offset and subclass members |

If a game update breaks the layout, rerun these against the new build and update the ini.

## Versions
- LORT build `++BigWalk+release-CL-24629` (Steam, October 2026), engine 5.7.
- UE4SS experimental `v3.0.1-1152-ge3ba1016`.

## Credits
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) team, MIT.
- Layout reverse-engineered with an AI coding agent, Claude, using
  [universal-modder](https://github.com/rehan-remade/universal-modder).
- No game files or decompiled code are included.
