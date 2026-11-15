---------------------------- MODULE RefreshOneShot ----------------------------
(***************************************************************************)
(* One agent "Refresh now" request against native Hermes cron, as written *)
(* in src/living-spaces/living_spaces_core/upkeep.py at the sync commit    *)
(* recorded in verification/formal/COVERAGE.json.                          *)
(*                                                                         *)
(* One refresh process walks refresh_now (upkeep.py:502-559) step by step. *)
(* Each step is one public cronjob_manage call or one SQLite transaction,  *)
(* the unit the code cannot split. The environment interleaves the native  *)
(* scheduler, the user's Pause/Remove/Archive/Delete, cron refusals and a  *)
(* DB failure after the run.                                               *)
(*                                                                         *)
(* Broken* constants reintroduce historical defects (a)-(d). All FALSE is  *)
(* the code at the sync commit.                                            *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS
    AllowLongRun,        \* explore an inline run that outlasts ONE_SHOT_SLOT (upkeep.py:19-24 residual)
    BrokenNoResume,      \* (a) run the born-paused one-shot without resuming it
    BrokenNoSkipCheck,   \* (a) report ok although the native run was skipped
    BrokenNoConsume,     \* (b) leave the once slot pending after a manual inline run
    BrokenNoBackgroundConsume, \* (c) background run leaves the one-shot enabled
    BrokenNoPostRunCleanup,    \* (c) DB error after the run leaves the one-shot enabled
    BrokenSlotDueAtCreate      \* (d) one-shot created already due

VARIABLES
    env,         \* the environment for this behaviour, fixed at Init (see Env)
    pc,          \* refresh process step
    created,     \* this invocation owns a new one-shot (upkeep.py:508)
    job,         \* native record of the job the request runs
    slotDue,     \* wall clock has reached the pending once slot
    reply,       \* native run reply kind
    err,         \* the error the process is propagating, if any
    pauseFailed, \* cleanup or consume pause refused
    result,      \* what the caller is told
    warned,      \* the reply says the job may run again
    manualRan,   \* the manual run itself executed (inline or background start)
    execs,       \* executions of the job attributable to this request
    okExecs,     \* successful executions
    space,       \* Space status
    userBudget   \* user actions left (bounds the model)

vars == <<env, pc, created, job, slotDue, reply, err, pauseFailed, result, warned,
          manualRan, execs, okExecs, space, userBudget>>

(* Linked: the Space already has a linked agent job (upkeep.py:507-513). linkedEnabled: that job is   *)
(* enabled. longRun: an inline run outlasts the 7-day slot. cronFailures: public cron                *)
(* resume/pause/remove/list may refuse (upkeep.py:115-126). dbFailure: the post-run SQLite recheck    *)
(* raises (upkeep.py:453-457).                                                                       *)
Env == [linked : BOOLEAN, linkedEnabled : BOOLEAN,
        longRun : IF AllowLongRun THEN BOOLEAN ELSE {FALSE},
        cronFailures : BOOLEAN, dbFailure : BOOLEAN]

Linked == env.linked
LinkedEnabled == env.linkedEnabled
LongRun == env.longRun
CronFailures == env.cronFailures
DbFailure == env.dbFailure

NoJob == [exists |-> FALSE, enabled |-> FALSE, pending |-> FALSE]

Init ==
    /\ env \in Env
    /\ pc = "start"
    /\ created = ~Linked
    /\ job = IF Linked THEN [exists |-> TRUE, enabled |-> LinkedEnabled, pending |-> TRUE] ELSE NoJob
    /\ slotDue = FALSE
    /\ reply = "none"
    /\ err = "none"
    /\ pauseFailed = FALSE
    /\ result = "pending"
    /\ warned = FALSE
    /\ manualRan = FALSE
    /\ execs = 0
    /\ okExecs = 0
    /\ space = "active"
    /\ userBudget = 1

(* upkeep.py:503-513: one db.write() transaction. An archived Space refuses (505-506). A fresh  *)
(* request creates a paused one-shot named living-spaces:<sid>:once with slot ONE_SHOT_SLOT.    *)
Create ==
    /\ pc = "start"
    /\ IF space # "active"
         THEN /\ pc' = "done" /\ result' = "err_other"
              /\ UNCHANGED <<job, slotDue>>
         ELSE /\ pc' = IF created /\ ~BrokenNoResume THEN "resume" ELSE "run"
              /\ result' = result
              /\ IF created
                   THEN /\ job' = [exists |-> TRUE, enabled |-> FALSE, pending |-> TRUE]
                        /\ slotDue' = BrokenSlotDueAtCreate
                   ELSE UNCHANGED <<job, slotDue>>
    /\ UNCHANGED <<created, reply, err, pauseFailed, warned, manualRan, execs, okExecs, space, userBudget>>

(* upkeep.py:516-517 -> _mutate("resume") upkeep.py:139-180: resume, then verify enabled.       *)
Resume ==
    /\ pc = "resume"
    /\ IF job.exists
         THEN \/ /\ job' = [job EXCEPT !.enabled = TRUE] /\ pc' = "run" /\ err' = err
              \/ /\ CronFailures /\ job' = job /\ pc' = "cleanup_pause" /\ err' = "pre_run"
         ELSE /\ job' = job /\ pc' = "cleanup_pause" /\ err' = "pre_run"
    /\ UNCHANGED <<created, slotDue, reply, pauseFailed, result, warned, manualRan, execs, okExecs, space, userBudget>>

(* upkeep.py:519 -> _run_now upkeep.py:443 -> _mutate("run"). Native semantics from Hermes       *)
(* tools/cronjob_tools.py _action_run: a missing job is refused, a paused job is skipped with   *)
(* executed=False, otherwise the run executes inline (ok or failed) or starts in the background. *)
(* A manual run is an extra fire: the once slot stays pending (test_agent_refresh_dispatch.py). *)
Run ==
    /\ pc = "run"
    /\ IF ~job.exists
         THEN /\ reply' = "refused" /\ err' = "refused" /\ pc' = "cleanup_pause"
              /\ UNCHANGED <<execs, okExecs, manualRan, slotDue>>
         ELSE IF ~job.enabled
         THEN /\ reply' = "skipped" /\ err' = err /\ pc' = "postcheck"
              /\ UNCHANGED <<execs, okExecs, manualRan, slotDue>>
         ELSE \/ /\ reply' = "inline_ok" /\ execs' = execs + 1 /\ okExecs' = okExecs + 1
                 /\ manualRan' = TRUE /\ err' = err /\ pc' = "postcheck"
                 /\ slotDue' = (slotDue \/ LongRun)
              \/ /\ reply' = "inline_fail" /\ execs' = execs + 1 /\ okExecs' = okExecs
                 /\ manualRan' = TRUE /\ err' = err /\ pc' = "postcheck"
                 /\ slotDue' = (slotDue \/ LongRun)
              \/ /\ reply' = "background" /\ execs' = execs + 1 /\ okExecs' = okExecs + 1
                 /\ manualRan' = TRUE /\ err' = err /\ pc' = "postcheck" /\ slotDue' = slotDue
    /\ UNCHANGED <<created, job, pauseFailed, result, warned, space, userBudget>>

(* _mutate("run") verifies with a list after the run (upkeep.py:149-155); then _run_now rechecks *)
(* the Space in its own db.write() (upkeep.py:446-457). Archived: pause; deleted: remove.       *)
PostCheck ==
    /\ pc = "postcheck"
    /\ \/ /\ CronFailures /\ err' = "verify_refused" /\ pc' = "cleanup_pause"   \* reason native_refused, upkeep.py:149-155
          /\ UNCHANGED <<job>>
       \/ /\ DbFailure /\ err' = "post_run" /\ job' = job
          /\ pc' = IF BrokenNoPostRunCleanup THEN "return_error" ELSE "cleanup_pause"
       \/ /\ space = "archived" /\ err' = "post_run" /\ pc' = "cleanup_pause"
          /\ job' = [job EXCEPT !.enabled = FALSE]
       \/ /\ space = "deleted" /\ err' = "post_run" /\ pc' = "cleanup_pause"
          /\ job' = NoJob
       \/ /\ space = "active" /\ err' = err /\ job' = job /\ pc' = "skipcheck"
    /\ UNCHANGED <<created, slotDue, reply, pauseFailed, result, warned, manualRan, execs, okExecs, space, userBudget>>

(* upkeep.py:520-525: executed=False, execution_skipped or execution_success=False is refused.  *)
SkipCheck ==
    /\ pc = "skipcheck"
    /\ IF reply \in {"skipped", "inline_fail"} /\ ~BrokenNoSkipCheck
         THEN /\ err' = "refused" /\ pc' = "cleanup_pause"
         ELSE /\ err' = err
              /\ pc' = IF created /\ reply = "inline_ok" /\ ~BrokenNoConsume THEN "consume_pause"
                       ELSE IF created /\ reply = "background" /\ ~BrokenNoBackgroundConsume THEN "consume_pause"
                       ELSE "return_ok"
    /\ UNCHANGED <<created, job, slotDue, reply, pauseFailed, result, warned, manualRan, execs, okExecs, space, userBudget>>

(* Error path, created only (upkeep.py:526-550): pause, then remove if still listed.             *)
CleanupPause ==
    /\ pc = "cleanup_pause"
    /\ IF ~created
         THEN /\ pc' = "return_error" /\ job' = job /\ pauseFailed' = pauseFailed
         ELSE IF job.exists
         THEN \/ /\ job' = [job EXCEPT !.enabled = FALSE] /\ pauseFailed' = FALSE /\ pc' = "cleanup_remove"
              \/ /\ CronFailures /\ job' = job /\ pauseFailed' = TRUE /\ pc' = "cleanup_remove"
         ELSE /\ job' = job /\ pauseFailed' = TRUE /\ pc' = "cleanup_remove"
    /\ UNCHANGED <<created, slotDue, reply, err, result, warned, manualRan, execs, okExecs, space, userBudget>>

CleanupRemove ==
    /\ pc = "cleanup_remove"
    /\ IF job.exists
         THEN \/ /\ job' = NoJob /\ pc' = "return_error" /\ warned' = warned
              \/ /\ CronFailures /\ job' = job /\ pc' = "return_error"
                 /\ warned' = (warned \/ pauseFailed)     \* upkeep.py:540-543 "may still be enabled"
         ELSE /\ job' = job /\ pc' = "return_error" /\ warned' = warned
    /\ UNCHANGED <<created, slotDue, reply, err, pauseFailed, result, manualRan, execs, okExecs, space, userBudget>>

(* _consume_one_shot upkeep.py:562-588: pause; background stops there; inline also removes.     *)
ConsumePause ==
    /\ pc = "consume_pause"
    /\ IF job.exists
         THEN \/ /\ job' = [job EXCEPT !.enabled = FALSE] /\ pauseFailed' = FALSE
              \/ /\ CronFailures /\ job' = job /\ pauseFailed' = TRUE
         ELSE /\ job' = job /\ pauseFailed' = TRUE
    /\ pc' = IF reply = "background" THEN "consume_background" ELSE "consume_remove"
    /\ UNCHANGED <<created, slotDue, reply, err, result, warned, manualRan, execs, okExecs, space, userBudget>>

ConsumeBackground ==
    /\ pc = "consume_background"
    /\ IF pauseFailed
         THEN /\ pc' = "return_error" /\ err' = "post_run" /\ warned' = TRUE   \* upkeep.py:573-577
         ELSE /\ pc' = "return_ok" /\ err' = err /\ warned' = warned
    /\ UNCHANGED <<created, job, slotDue, reply, pauseFailed, result, manualRan, execs, okExecs, space, userBudget>>

ConsumeRemove ==
    /\ pc = "consume_remove"
    /\ IF job.exists
         THEN \/ /\ job' = NoJob /\ pc' = "return_ok" /\ err' = err /\ warned' = warned
              \/ /\ CronFailures /\ job' = job
                 /\ IF pauseFailed
                      THEN pc' = "return_error" /\ err' = "post_run" /\ warned' = TRUE  \* upkeep.py:584-588
                      ELSE pc' = "return_ok" /\ err' = err /\ warned' = warned         \* upkeep.py:582-583
         ELSE /\ job' = job /\ pc' = "return_ok" /\ err' = err /\ warned' = warned
    /\ UNCHANGED <<created, slotDue, reply, pauseFailed, result, manualRan, execs, okExecs, space, userBudget>>

ReturnOk ==
    /\ pc = "return_ok" /\ pc' = "done" /\ result' = "ok"
    /\ UNCHANGED <<created, job, slotDue, reply, err, pauseFailed, warned, manualRan, execs, okExecs, space, userBudget>>

ReturnError ==
    /\ pc = "return_error" /\ pc' = "done"
    /\ result' = CASE err = "refused" -> "err_refused"
                    [] err = "verify_refused" -> "err_verify_refused"
                    [] OTHER -> "err_other"
    /\ UNCHANGED <<created, job, slotDue, reply, err, pauseFailed, warned, manualRan, execs, okExecs, space, userBudget>>

(* Environment. The once slot is 7 days out: the clock reaches it only after the request has    *)
(* returned, unless a run outlasts it (LongRun) or the slot was due at creation (variant d).    *)
ClockReachesSlot ==
    /\ ~slotDue /\ job.exists /\ job.pending /\ pc = "done"
    /\ slotDue' = TRUE
    /\ UNCHANGED <<pc, created, job, reply, err, pauseFailed, result, warned, manualRan, execs, okExecs, space, userBudget>>

(* Hermes scheduler fire of a due one-shot: runs it and spends repeat=1, retiring the record.    *)
(* Never during this request's own inline run, because the manual run holds the claim.          *)
SchedulerFire ==
    /\ created
    /\ job.exists /\ job.enabled /\ job.pending /\ slotDue
    /\ pc # "postcheck"
    /\ job' = [exists |-> TRUE, enabled |-> FALSE, pending |-> FALSE]
    /\ execs' = execs + 1 /\ okExecs' = okExecs + 1
    /\ UNCHANGED <<pc, created, slotDue, reply, err, pauseFailed, result, warned, manualRan, space, userBudget>>

(* upkeep_action pause/remove act on every owned job, the one-shot included (upkeep.py:476-489). *)
UserPause ==
    /\ userBudget > 0 /\ job.exists /\ job.enabled
    /\ job' = [job EXCEPT !.enabled = FALSE] /\ userBudget' = userBudget - 1
    /\ UNCHANGED <<pc, created, slotDue, reply, err, pauseFailed, result, warned, manualRan, execs, okExecs, space>>

UserRemove ==
    /\ userBudget > 0 /\ job.exists
    /\ job' = NoJob /\ userBudget' = userBudget - 1
    /\ UNCHANGED <<pc, created, slotDue, reply, err, pauseFailed, result, warned, manualRan, execs, okExecs, space>>

(* set_status archive pauses owned jobs in the same transaction (projects.py:433-441,           *)
(* upkeep.py:591-600). It cannot run inside refresh_now's create transaction.                   *)
UserArchive ==
    /\ userBudget > 0 /\ space = "active" /\ pc # "start"
    /\ space' = "archived" /\ userBudget' = userBudget - 1
    /\ job' = IF job.exists THEN [job EXCEPT !.enabled = FALSE] ELSE job
    /\ UNCHANGED <<pc, created, slotDue, reply, err, pauseFailed, result, warned, manualRan, execs, okExecs>>

(* delete_space removes owned jobs in its transaction (projects.py:449-465, upkeep.py:603-614).  *)
UserDelete ==
    /\ userBudget > 0 /\ space # "deleted" /\ pc # "start"
    /\ space' = "deleted" /\ userBudget' = userBudget - 1
    /\ job' = NoJob
    /\ UNCHANGED <<pc, created, slotDue, reply, err, pauseFailed, result, warned, manualRan, execs, okExecs>>

Finished ==
    /\ pc = "done"
    /\ ~(created /\ job.exists /\ job.enabled /\ job.pending)
    /\ UNCHANGED vars

Next ==
  /\ env' = env
  /\ \/ Create \/ Resume \/ Run \/ PostCheck \/ SkipCheck
     \/ CleanupPause \/ CleanupRemove \/ ConsumePause \/ ConsumeBackground \/ ConsumeRemove
     \/ ReturnOk \/ ReturnError
     \/ ClockReachesSlot \/ SchedulerFire
     \/ UserPause \/ UserRemove \/ UserArchive \/ UserDelete
     \/ Finished

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ execs \in 0..3 /\ okExecs \in 0..3 /\ userBudget \in 0..1
    /\ result \in {"pending", "ok", "err_refused", "err_verify_refused", "err_other"}

(* A fresh refresh request executes upkeep at most once, unless its own reply warns that the     *)
(* one-shot may run again.                                                                      *)
AtMostOnce == (created /\ ~warned) => execs <= 1

(* A refresh reported as successful really ran: the manual run executed and did not fail.        *)
NoSuccessForSkippedRun == result = "ok" => (manualRan /\ reply \in {"inline_ok", "background"})

(* A refresh reported as refused ("Hermes cron did not complete the refresh execution") had no   *)
(* successful execution on behalf of this request, unless its reply warns the one-shot may still *)
(* be enabled (upkeep.py:540-549).                                                              *)
NoFalseRefusal == (result = "err_refused" /\ ~warned) => okExecs = 0
(* Finding F1, checked separately: a run that succeeded is not reported as refused when only the   *)
(* job-list verification after it was refused.                                                  *)
NoRefusalAfterSuccessfulRun == (result = "err_verify_refused" /\ ~warned) => okExecs = 0
=============================================================================
