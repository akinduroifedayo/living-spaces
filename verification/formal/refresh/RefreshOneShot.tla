---------------------------- MODULE RefreshOneShot ----------------------------
(***************************************************************************)
(* Bounded abstraction of upkeep.py at released 4aea12d. All source line    *)
(* references below are to src/living-spaces/living_spaces_core/{file}.     *)
(* Native mutations, their list readbacks, and the Space DB recheck are     *)
(* separate actions. dbOwner serializes SQLite writers, NOT native cron.   *)
(* A native effect survives a refused list and a rolled-back DB operation. *)
(*                                                                         *)
(* Native claim/extra-fire/due semantics are ASSUMPTIONS from Hermes        *)
(* a317c07 and tests/python/test_agent_refresh_dispatch.py:53-157,541-569,  *)
(* not properties proved here. A manual fire does not spend repeat=1.      *)
(* Invocation/claim, execution, claim release, and reply are separate.     *)
(* Scheduler claim, execution, and retirement are likewise separate.       *)
(* Background start counts an invocation, never successful completion.     *)
(* Background release abstracts completion/cancellation with unknown       *)
(* outcome; it adds no okExecs. Scheduler success/failure is nondeterministic.*)
(*                                                                         *)
(* Bounds: one refresh, one job, at most one user pause/remove/archive/    *)
(* delete. Only invocation-owned fresh jobs have scheduler fires; recurring*)
(* linked-job scheduling is OUTSIDE AtMostOnce and outside this model.     *)
(* A successful paused create plus its DB commit is collapsed in Create.  *)
(* This is invisible to these actors while the SQLite writer excludes     *)
(* user actions and the paused job cannot fire. Create/DB-commit failures, *)
(* orphan discovery, other jobs, multiple requests, native lost-ack effects,*)
(* crashes, timeouts and historical dispatch-limit retirement are omitted. *)
(* Accepted forwarded/unknown replies, supported by the product, are       *)
(* explicitly BOUNDED OUT. No completion is inferred from their absence.   *)
(*                                                                         *)
(* User lifecycle is a ONE-JOB slice: list, mutate, verify, final list, DB  *)
(* commit or abort. It preserves native effects on verification failure.   *)
(* Shim/filesystem failures, cancellation side effects, multiple targets,  *)
(* and lifecycle DB commit failures are omitted. This is NOT a full        *)
(* archive/delete or cross-store atomicity proof. The archived/deleted     *)
(* _run_now recheck holds its DB writer across separate native calls.      *)
(* Local computation between calls is folded into the preceding read or   *)
(* reply. List reads are assumed coherent snapshots; no stale list cache.  *)
(*                                                                         *)
(* Normally the seven-day slot is reached only after the reply. AllowLongRun*)
(* advances it during an inline execution. No other mid-request wall-clock*)
(* delays are explored. Broken* flags are negative controls, not exact     *)
(* reconstructions of every historical defect. In particular (d) explores *)
(* due-at-resume scheduling followed by a manual skip/refusal, NOT the     *)
(* historical dispatch-limit-mid-run retirement in upkeep.py:22-23.       *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS
    FreshOnly,
    NoUserAction,
    AllowLongRun,
    BrokenNoResume,
    BrokenNoSkipCheck,
    BrokenNoConsume,
    BrokenNoBackgroundConsume,
    BrokenNoPostRunCleanup,
    BrokenSlotDueAtCreate

VARIABLES
    env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed,
    result, warned, manualRan, execs, okExecs, space, userBudget,
    claim, userPc, userOp, dbOwner

vars == <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed,
          result, warned, manualRan, execs, okExecs, space, userBudget,
          claim, userPc, userOp, dbOwner>>

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
    /\ (~FreshOnly \/ ~env.linked)
    /\ pc = "start"
    /\ created = ~Linked
    /\ job = IF Linked THEN [exists |-> TRUE, enabled |-> LinkedEnabled, pending |-> TRUE] ELSE NoJob
    /\ slotDue = FALSE
    /\ reply = "none"
    /\ err = "none"
    /\ pauseFailed = FALSE
    /\ removeFailed = FALSE
    /\ result = "pending"
    /\ warned = FALSE
    /\ manualRan = FALSE
    /\ execs = 0
    /\ okExecs = 0
    /\ space = "active"
    /\ userBudget = 1
    /\ claim = "none"
    /\ userPc = "idle"
    /\ userOp = "none"
    /\ dbOwner = "none"

(* upkeep.py:503-514,183-190. Successful paused create/readback/DB commit    *)
(* only, collapsed under the explicit creation bounds above.              *)
Create ==
    /\ pc = "start" /\ dbOwner = "none"
    /\ IF space # "active"
         THEN /\ pc' = "done" /\ result' = "err_other"
              /\ UNCHANGED <<job, slotDue>>
         ELSE /\ pc' = IF created /\ ~BrokenNoResume THEN "resume" ELSE "run"
              /\ result' = result
              /\ IF created
                   THEN /\ job' = [exists |-> TRUE, enabled |-> FALSE, pending |-> TRUE]
                        /\ slotDue' = BrokenSlotDueAtCreate
                   ELSE UNCHANGED <<job, slotDue>>
    /\ UNCHANGED <<env, created, reply, err, pauseFailed, removeFailed, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:517 -> 143. Native resume effect/refusal, not its readback.    *)
Resume ==
    /\ pc = "resume"
    /\ \/ /\ job.exists /\ job' = [job EXCEPT !.enabled = TRUE]
          /\ pc' = "resume_verify" /\ err' = err
       \/ /\ (~job.exists \/ CronFailures) /\ job' = job
          /\ pc' = "cleanup_pause" /\ err' = "pre_run"
    /\ UNCHANGED <<env, created, slotDue, reply, pauseFailed, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:149-150,173-180. A successful resume can fail verification.    *)
ResumeVerify ==
    /\ pc = "resume_verify"
    /\ \/ /\ job.exists /\ job.enabled /\ pc' = "run" /\ err' = err
       \/ /\ (~job.exists \/ ~job.enabled \/ CronFailures)
          /\ pc' = "cleanup_pause" /\ err' = "pre_run"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:443 ->143; assumed native _action_run eligibility/claim.       *)
Run ==
    /\ pc = "run"
    /\ IF ~job.exists
         THEN /\ reply' = "refused" /\ err' = "refused" /\ pc' = "cleanup_pause" /\ claim' = claim
         ELSE IF ~job.enabled \/ claim # "none"
         THEN /\ reply' = "skipped" /\ err' = err /\ pc' = "run_verify" /\ claim' = claim
         ELSE /\ reply' = reply /\ err' = err /\ pc' = "run_execute" /\ claim' = "manual"
    /\ UNCHANGED <<env, created, job, slotDue, pauseFailed, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner>>

(* upkeep.py:443 native execution boundary; tests:74-101. This counts a    *)
(* dispatch once; only inline_ok establishes successful completion.        *)
RunExecute ==
    /\ pc = "run_execute" /\ claim = "manual"
    /\ \/ /\ reply' = "inline_ok" /\ okExecs' = okExecs + 1
          /\ pc' = "run_release" /\ claim' = claim /\ slotDue' = (slotDue \/ LongRun)
       \/ /\ reply' = "inline_fail" /\ okExecs' = okExecs
          /\ pc' = "run_release" /\ claim' = claim /\ slotDue' = (slotDue \/ LongRun)
       \/ /\ reply' = "background" /\ okExecs' = okExecs
          /\ pc' = "run_reply" /\ claim' = "background" /\ slotDue' = slotDue
    /\ execs' = execs + 1 /\ manualRan' = TRUE
    /\ UNCHANGED <<env, created, job, err, pauseFailed, removeFailed, result, warned,
                    space, userBudget, userPc, userOp, dbOwner>>

(* upkeep.py:443 native return boundary; tests:89-101. Scheduler may claim  *)
(* after the manual claim clears, BEFORE the plugin sees the run reply.    *)
RunRelease ==
    /\ pc = "run_release" /\ claim = "manual"
    /\ pc' = "run_reply" /\ claim' = "none"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner>>

(* upkeep.py:143 returns before the separate _jobs call at 150.            *)
RunReply ==
    /\ pc = "run_reply" /\ pc' = "run_verify"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:149-155,175-176. Absence is valid for run; list refusal is not. *)
RunVerify ==
    /\ pc = "run_verify"
    /\ \/ /\ pc' = "db_recheck" /\ err' = err
       \/ /\ CronFailures /\ pc' = "cleanup_pause" /\ err' = "verify_refused"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:446-457. The Space DB read is AFTER the native list. Archived  *)
(* or deleted cleanup holds the DB writer but does not make cron atomic.   *)
DBRecheck ==
    /\ pc = "db_recheck" /\ dbOwner = "none"
    /\ \/ /\ DbFailure /\ err' = "post_run" /\ dbOwner' = "none"
          /\ pc' = IF BrokenNoPostRunCleanup THEN "return_error" ELSE "cleanup_pause"
       \/ /\ space # "active" /\ err' = "post_run" /\ pc' = "recheck_list" /\ dbOwner' = "refresh"
       \/ /\ space = "active" /\ err' = err /\ pc' = "skipcheck" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp>>

(* upkeep.py:449. This read is separate from both DBRecheck and mutation.  *)
RecheckList ==
    /\ pc = "recheck_list" /\ dbOwner = "refresh"
    /\ \/ /\ job.exists /\ pc' = IF space = "deleted" THEN "recheck_remove" ELSE "recheck_pause"
          /\ dbOwner' = dbOwner
       \/ /\ (~job.exists \/ CronFailures) /\ pc' = "cleanup_pause" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp>>

(* upkeep.py:520-525,553-558. Only evidenced inline/background execution    *)
(* modes are in this model; accepted unknown/forwarded replies are omitted.*)
SkipCheck ==
    /\ pc = "skipcheck"
    /\ IF reply \in {"skipped", "inline_fail"} /\ ~BrokenNoSkipCheck
         THEN /\ err' = "refused" /\ pc' = "cleanup_pause"
         ELSE /\ err' = err
              /\ pc' = IF created /\ reply = "inline_ok" /\ ~BrokenNoConsume THEN "consume_pause"
                       ELSE IF created /\ reply = "background" /\ ~BrokenNoBackgroundConsume THEN "consume_pause"
                       ELSE "return_ok"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:527. Existing linked jobs are not invocation-owned cleanup.   *)
CleanupLinked ==
    /\ pc = "cleanup_pause" /\ ~created /\ pc' = "return_error"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

PauseStages == {"cleanup_pause", "consume_pause", "recheck_pause"}
PauseVerifyStage(p) == CASE p = "cleanup_pause" -> "cleanup_pause_verify"
                           [] p = "consume_pause" -> "consume_pause_verify"
                           [] OTHER -> "recheck_pause_verify"
PauseDoneStage(p) == CASE p \in {"cleanup_pause", "cleanup_pause_verify"} -> "cleanup_paused"
                         [] p \in {"consume_pause", "consume_pause_verify"} -> "consume_paused"
                         [] OTHER -> "recheck_paused"

(* upkeep.py:530,567,450 ->143. The pause call alone may succeed or refuse. *)
NativePause ==
    /\ pc \in PauseStages /\ (pc # "cleanup_pause" \/ created)
    /\ \/ /\ job.exists /\ job' = [job EXCEPT !.enabled = FALSE]
          /\ pauseFailed' = FALSE /\ pc' = PauseVerifyStage(pc)
       \/ /\ (~job.exists \/ CronFailures) /\ job' = job
          /\ pauseFailed' = TRUE /\ pc' = PauseDoneStage(pc)
    /\ UNCHANGED <<env, created, slotDue, reply, err, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:149-150,171-180. Native pause succeeded, readback may fail.     *)
NativePauseVerify ==
    /\ pc \in {"cleanup_pause_verify", "consume_pause_verify", "recheck_pause_verify"}
    /\ \/ /\ job.exists /\ ~job.enabled /\ pauseFailed' = FALSE
       \/ /\ (~job.exists \/ job.enabled \/ CronFailures) /\ pauseFailed' = TRUE
    /\ pc' = PauseDoneStage(pc)
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:531-534,568-577,450-454. Release recheck's DB writer on error. *)
PauseDone ==
    /\ pc \in {"cleanup_paused", "consume_paused", "recheck_paused"}
    /\ CASE pc = "cleanup_paused" -> /\ pc' = "cleanup_list" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
         [] pc = "recheck_paused" -> /\ pc' = "cleanup_pause" /\ err' = err /\ warned' = warned /\ dbOwner' = "none"
         [] pc = "consume_paused" /\ reply = "background" /\ pauseFailed ->
              /\ pc' = "return_error" /\ err' = "post_run" /\ warned' = TRUE /\ dbOwner' = dbOwner
         [] pc = "consume_paused" /\ reply = "background" /\ ~pauseFailed ->
              /\ pc' = "return_ok" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
         [] OTHER -> /\ pc' = "consume_remove" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp>>

(* upkeep.py:534-549. The preliminary cleanup list can independently fail. *)
CleanupList ==
    /\ pc = "cleanup_list"
    /\ \/ /\ job.exists /\ pc' = "cleanup_remove" /\ err' = err /\ warned' = warned
       \/ /\ ~job.exists /\ pc' = "return_error" /\ err' = err /\ warned' = warned
       \/ /\ CronFailures /\ pc' = "return_error" /\ err' = "post_run" /\ warned' = (warned \/ pauseFailed)
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

RemoveVerifyStage(p) == CASE p = "cleanup_remove" -> "cleanup_remove_verify"
                            [] p = "consume_remove" -> "consume_remove_verify"
                            [] OTHER -> "recheck_remove_verify"
RemoveDoneStage(p) == CASE p = "cleanup_remove_verify" -> "cleanup_removed"
                          [] p = "consume_remove_verify" -> "consume_removed"
                          [] OTHER -> "recheck_removed"

(* upkeep.py:535,579,450 ->143-148. Even native remove refusal is followed *)
(* by a separate readback; absence reconciles an already-absent job.       *)
NativeRemove ==
    /\ pc \in {"cleanup_remove", "consume_remove", "recheck_remove"}
    /\ \/ job' = NoJob
       \/ /\ CronFailures /\ job' = job
    /\ pc' = RemoveVerifyStage(pc)
    /\ UNCHANGED <<env, created, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:149-170. Effect succeeded then verification refused is allowed.*)
NativeRemoveVerify ==
    /\ pc \in {"cleanup_remove_verify", "consume_remove_verify", "recheck_remove_verify"}
    /\ \/ /\ ~job.exists /\ removeFailed' = FALSE
       \/ /\ (job.exists \/ CronFailures) /\ removeFailed' = TRUE
    /\ pc' = RemoveDoneStage(pc)
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:536-550,580-588,450-454. Cleanup failure's top-level reason is *)
(* cron_cleanup_failed, NOT the original native_refused (546-549).         *)
RemoveDone ==
    /\ pc \in {"cleanup_removed", "consume_removed", "recheck_removed"}
    /\ CASE pc = "recheck_removed" ->
              /\ pc' = "cleanup_pause" /\ dbOwner' = "none" /\ err' = err /\ warned' = warned
         [] pc = "cleanup_removed" ->
              /\ pc' = "return_error" /\ dbOwner' = dbOwner
              /\ err' = IF removeFailed THEN "post_run" ELSE err
              /\ warned' = (warned \/ (removeFailed /\ pauseFailed))
         [] OTHER ->
              /\ pc' = IF removeFailed /\ pauseFailed THEN "return_error" ELSE "return_ok"
              /\ dbOwner' = dbOwner
              /\ err' = IF removeFailed /\ pauseFailed THEN "post_run" ELSE err
              /\ warned' = (warned \/ (removeFailed /\ pauseFailed))
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp>>

(* upkeep.py:552-559. result=ok is dispatch acceptance, not background completion.*)
ReturnOk ==
    /\ pc = "return_ok" /\ pc' = "done" /\ result' = "ok"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:125,154-155,524-550,573-588. Distinguish the refusal diagnostic *)
(* from verification refusal and all post-run/cleanup errors.              *)
ReturnError ==
    /\ pc = "return_error" /\ pc' = "done"
    /\ result' = CASE err = "refused" -> "err_refused"
                    [] err = "verify_refused" -> "err_verify_refused"
                    [] OTHER -> "err_other"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:19-24. Bounded clock; all other long external-call delays omitted.*)
ClockReachesSlot ==
    /\ ~slotDue /\ job.exists /\ job.pending /\ pc = "done" /\ slotDue' = TRUE
    /\ UNCHANGED <<env, pc, created, job, reply, err, pauseFailed, removeFailed, result, warned,
                    manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner>>

(* upkeep.py:19-23; native assumption, tests:140-157. Only fresh once jobs. *)
SchedulerClaim ==
    /\ created /\ job.exists /\ job.enabled /\ job.pending /\ slotDue /\ claim = "none"
    /\ claim' = "scheduler"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner>>

(* Same native assumption. Already claimed work may run despite a pause.  *)
(* Cancellation on remove is abstracted conservatively as may still run.  *)
SchedulerExecute ==
    /\ claim = "scheduler" /\ claim' = "scheduler_settle" /\ execs' = execs + 1
    /\ okExecs' \in {okExecs, okExecs + 1}
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, space, userBudget, userPc, userOp, dbOwner>>

(* Same native assumption. Scheduled completion spends repeat=1; a removed*)
(* native record is never recreated by settling. Not dispatch-limit retirement.*)
SchedulerRetire ==
    /\ claim = "scheduler_settle" /\ claim' = "none"
    /\ job' = IF job.exists THEN [exists |-> TRUE, enabled |-> FALSE, pending |-> FALSE] ELSE job
    /\ UNCHANGED <<env, pc, created, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner>>

(* upkeep.py:563-564; tests:74-77,528-539. Unknown background outcome.      *)
BackgroundRelease ==
    /\ claim = "background" /\ claim' = "none"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner>>

(* upkeep.py:466-486; projects.py:433-441,456-465. Start one SQLite writer;  *)
(* the user operation's public cron calls are NOT inside one model action. *)
UserStart ==
    /\ ~NoUserAction
    /\ userBudget > 0 /\ dbOwner = "none"
    /\ userOp' \in {"pause", "remove", "archive", "delete"}
    /\ space # "deleted" /\ (userOp' # "archive" \/ space = "active")
    /\ userBudget' = userBudget - 1 /\ userPc' = "list" /\ dbOwner' = "user"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, claim>>

UserRemoves == userOp \in {"remove", "delete"}

(* upkeep.py:477,594,607. A one-job ownership snapshot. More targets omitted.*)
UserList ==
    /\ userPc = "list" /\ dbOwner = "user"
    /\ \/ userPc' = IF job.exists THEN "mutate" ELSE "final_list"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userOp, dbOwner>>

(* upkeep.py:482,596,609 ->143. Abort cannot roll back this native effect.  *)
UserMutate ==
    /\ userPc = "mutate" /\ dbOwner = "user"
    /\ \/ /\ (job.exists \/ UserRemoves)
          /\ job' = IF UserRemoves THEN NoJob ELSE [job EXCEPT !.enabled = FALSE]
          /\ userPc' = "verify"
       \/ /\ (~job.exists \/ CronFailures) /\ job' = job
          /\ userPc' = IF UserRemoves THEN "verify" ELSE "abort"
    /\ UNCHANGED <<env, pc, created, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userOp, dbOwner>>

UserValid == IF UserRemoves THEN ~job.exists ELSE job.exists /\ ~job.enabled

(* upkeep.py:149-180. A native effect followed by a refused list aborts DB. *)
UserVerify ==
    /\ userPc = "verify" /\ dbOwner = "user"
    /\ \/ userPc' = IF UserValid THEN "final_list" ELSE "abort"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userOp, dbOwner>>

(* upkeep.py:483-486,597-600,610-611. Absence also satisfies final pause.    *)
UserFinalList ==
    /\ userPc = "final_list" /\ dbOwner = "user"
    /\ \/ userPc' = IF ~job.exists \/ (~UserRemoves /\ ~job.enabled) THEN "commit" ELSE "abort"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userOp, dbOwner>>

(* projects.py:440-444,464; upkeep.py:487-489. DB commit is separate from    *)
(* every native call; only the Space status is retained by this slice.     *)
UserCommit ==
    /\ userPc = "commit" /\ dbOwner = "user"
    /\ space' = CASE userOp = "archive" -> "archived"
                    [] userOp = "delete" -> "deleted"
                    [] OTHER -> space
    /\ userPc' = "done" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, userBudget, claim, userOp>>

(* upkeep.py:486,599-600,611; caller's db.write rolls back DB, NOT cron.     *)
UserAbort ==
    /\ userPc = "abort" /\ dbOwner = "user"
    /\ userPc' = "done" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result,
                    warned, manualRan, execs, okExecs, space, userBudget, claim, userOp>>

(* upkeep.py:550,559. Stuttering only after the request and claimed work end.*)
Finished ==
    /\ pc = "done" /\ claim = "none" /\ dbOwner = "none"
    /\ ~(created /\ job.exists /\ job.enabled /\ job.pending)
    /\ UNCHANGED vars

Next ==
    \/ Create \/ Resume \/ ResumeVerify
    \/ Run \/ RunExecute \/ RunRelease \/ RunReply \/ RunVerify
    \/ DBRecheck \/ RecheckList \/ SkipCheck \/ CleanupLinked
    \/ NativePause \/ NativePauseVerify \/ PauseDone \/ CleanupList
    \/ NativeRemove \/ NativeRemoveVerify \/ RemoveDone
    \/ ReturnOk \/ ReturnError \/ ClockReachesSlot
    \/ SchedulerClaim \/ SchedulerExecute \/ SchedulerRetire \/ BackgroundRelease
    \/ UserStart \/ UserList \/ UserMutate \/ UserVerify \/ UserFinalList \/ UserCommit \/ UserAbort
    \/ Finished

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ execs \in 0..3 /\ okExecs \in 0..3 /\ userBudget \in 0..1
    /\ result \in {"pending", "ok", "err_refused", "err_verify_refused", "err_other"}

(* Fresh invocation-owned once jobs only; linked recurring jobs are excluded.*)
AtMostOnce == (created /\ ~warned) => execs <= 1

(* ok means evidenced dispatch, not successful background completion.      *)
NoSuccessForSkippedRun == result = "ok" => (manualRan /\ reply \in {"inline_ok", "background"})

(* Preserve the refusal properties. okExecs counts evidenced successful    *)
(* completions only, not accepted background/unknown/forwarded replies.     *)
NoFalseRefusal == (result = "err_refused" /\ ~warned) => okExecs = 0
NoRefusalAfterSuccessfulRun == (result = "err_verify_refused" /\ ~warned) => okExecs = 0
=============================================================================
