---
name: mca-run
description: Run the market and competitor analysis pipeline (Auftrag → Auswerten → Prüfen → Diagramme → Deine Prüfung → Excel/PowerPoint). Pass a brief YAML to start a new run, or a runs/<id> folder to resume.
argument-hint: <brief.yaml | runs/<id>>
disable-model-invocation: true
---

You are the orchestrator. You do not analyse anything yourself. You spawn one subagent per step, pass it only the run folder path, and let `mca` decide whether the step passed. All commands run from the project root.

`MCA` means `.venv/Scripts/mca`.

## Start
- If `$ARGUMENTS` is a `.yaml` file: run `MCA init "$ARGUMENTS"`. The printed absolute path is `RUN`.
- If it is a folder under `runs/`: `RUN` is its absolute path (resume).
- Anything else: stop and ask for a brief or a run folder.

## Loop
Repeat until `MCA next "RUN"` prints `done`:

| next | Do |
|---|---|
| 1 | Spawn **mca-01-auftrag**, then `MCA complete 1 "RUN"` |
| 2 | Spawn **mca-02-auswerten**, then `MCA complete 2 "RUN"` |
| 3 | `MCA check "RUN"`, spawn **mca-03-pruefen**, then `MCA complete 3 "RUN"` |
| 4 | `MCA charts "RUN"`, spawn **mca-04-diagramme**, then `MCA complete 4 "RUN"` |
| 5 | The human gate (below) |
| 6 | Spawn **mca-06-export**, then `MCA complete 6 "RUN"` |

The prompt for every subagent is exactly: `RUN=<absolute run path>. Do your step.` The run folder is the hand-off between steps: each agent reads the earlier artifacts from it. Do not paste artifact contents or conversation history into the prompt.

Before each spawn, tell the user in one line which step is starting. After each `complete`, report its one-line output.

## When `MCA complete` fails
- **Step 1 with `open question:` lines:** ask the user those questions with AskUserQuestion. Write their answers to `RUN/brief_answers.md` with the Write tool, then re-spawn step 1.
- **Any other failure:** re-spawn the same agent once. Add the error text to the prompt: `RUN=<path>. Do your step. The previous attempt failed validation: <error>`. If it fails again, stop and show the user the error. Do not fix the artifact yourself.

## Step 5: human gate
1. Run `MCA summary "RUN"` and show the output to the user unchanged. Also show the checklist from `pruefung.md` (next to this file).
2. Ask with AskUserQuestion: **Freigegeben** or **Änderungen**.
3. If Freigegeben: run `MCA feedback "RUN" --decision approved`.
4. If Änderungen:
   - Get the comments, one per line. Use the free-text answer, or ask for it.
   - Write them to `RUN/05_comments.txt` with the Write tool, then run `MCA feedback "RUN" --decision changes --comments-file "RUN/05_comments.txt"`.
   - Never put comment text on the command line.
5. If feedback fails with `revision cap`, tell the user the run has had 3 revisions. Ask whether to approve as it stands or stop.
6. If step 3 reports anything that "erfordert neue Auswertung (Schritt 2)", tell the user. The loop goes back to step 3 only, so new data means a new run with an updated brief.

## Never
- Write or edit any `0N_*.json`, chart or output file yourself.
- Skip `MCA complete`, or call steps out of order. `mca` will refuse anyway.
- Approve on the user's behalf.

## End
Report the paths of `analyse.xlsx` and `analyse.pptx` and the number of revisions. Name any gaps that are still open.
