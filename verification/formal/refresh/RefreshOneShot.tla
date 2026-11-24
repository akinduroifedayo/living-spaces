---------------------------- MODULE RefreshOneShot ----------------------------
(***************************************************************************)
(* Bounded abstraction of Refresh now at main 92486e1. Line references are *)
(* to src/living-spaces/living_spaces_core/{file}: upkeep.py refresh_now   *)
(* 765-871, _run_now 538-610, _cleanup_failed_refresh 736-762,             *)
(* _consume_one_shot 874-900, _mutate 148-185; maintenance.py acquire       *)
(* 313-338, fence 79-97, transaction 109-146, control 209-253,             *)
(* retire_resources 504-514; projects.py set_status 576-593, delete_space   *)
(* 596-617. Native mutations, their list readbacks, SQLite writers and the *)
(* Space fence are separate actions. dbOwner serializes SQLite writers     *)
(* (maintenance.transaction / db.write), NOT native cron. A native effect  *)
(* survives a refused list and a rolled-back writer.                       *)
(*                                                                         *)
(* Native claim/extra-fire/due semantics are ASSUMPTIONS from Hermes        *)
(* a317c07 and tests/python/test_agent_refresh_dispatch.py, not properties *)
(* proved here. A manual fire does not spend repeat=1. Invocation/claim,   *)
(* execution, claim release and reply are separate; so are scheduler claim,*)
(* execution and retirement. Background start counts an invocation, never  *)
(* successful completion; background release has unknown outcome.         *)
(*                                                                         *)
(* The refresh claim (maintenance.acquire) is taken before Init and is     *)
(* implicit. `retired` records that a user Upkeep remove or Space delete   *)
(* retired it (retire_resources, link_generation+1); the refresh's fences  *)
(* then fail with refresh_claim_lost / not_found ("stale", upkeep.py:802)  *)
(* and refresh_now does no cleanup of its own.                             *)
(*                                                                         *)
(* Bounds: one refresh, one job, at most one user pause/remove/archive/    *)
(* delete. Only invocation-owned fresh jobs have scheduler fires; recurring*)
(* linked-job scheduling is OUTSIDE AtMostOnce and outside this model.     *)
(* A successful paused create plus bind_job is collapsed in Create (one    *)
(* writer). Create/DB-commit failures other than the post-run receipt,     *)
(* orphan discovery, joined followers (other requests), other jobs, native *)
(* lost-ack effects, crashes, timeouts, forwarded or metadata-free         *)
(* ("unresolved") replies and dispatch-limit retirement are omitted.       *)
(*                                                                         *)
(* User lifecycle is a ONE-JOB slice: list, mutate, verify, final list, DB  *)
(* commit or abort, all inside one writer (maintenance.control envelope +  *)
(* transaction). Shim/filesystem failures, cancellation side effects,      *)
(* multiple targets and lifecycle DB commit failures are omitted.          *)
(* List reads are assumed coherent snapshots. The Space fence is a read    *)
(* (db.read) and needs no writer.                                          *)
(*                                                                         *)
(* Normally the seven-day slot is reached only after the reply. AllowLongRun*)
(* advances it during an inline execution. Broken* flags are negative      *)
(* controls, not exact reconstructions of every historical defect. (d)     *)
(* explores due-at-resume scheduling followed by a manual skip, NOT the    *)
(* historical dispatch-limit-mid-run retirement.                           *)
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
    BrokenSlotDueAtCreate,
    BrokenVerifyAsRefused

VARIABLES
    env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed,
    result, warned, manualRan, execs, okExecs, space, userBudget,
    claim, userPc, userOp, dbOwner,
    retired, dispatched, receiptErr, verifyFailed, lifecycle

vars == <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed,
          result, warned, manualRan, execs, okExecs, space, userBudget,
          claim, userPc, userOp, dbOwner,
          retired, dispatched, receiptErr, verifyFailed, lifecycle>>

refreshVars == <<pc, created, reply, err, pauseFailed, removeFailed, result, warned,
                 dispatched, receiptErr, verifyFailed, lifecycle>>
userVars == <<space, userBudget, userPc, userOp, retired>>

Env == [linked : BOOLEAN, linkedEnabled : BOOLEAN,
        longRun : IF AllowLongRun THEN BOOLEAN ELSE {FALSE},
        cronFailures : BOOLEAN, dbFailure : BOOLEAN]
Linked == env.linked
LinkedEnabled == env.linkedEnabled
LongRun == env.longRun
CronFailures == env.cronFailures
DbFailure == env.dbFailure
NoJob == [exists |-> FALSE, enabled |-> FALSE, pending |-> FALSE]

(* maintenance.py:79-97. not_found (incarnation) or refresh_claim_lost.     *)
FenceLost == space = "deleted" \/ retired
(* fence(..., work=True, archived=True): also refuses an archived Space.    *)
WorkFenceOk == ~FenceLost /\ space # "archived"
(* upkeep.py:794-795: no dispatch, or an explicit terminal native reply.   *)
Terminal == ~dispatched \/ reply \in {"inline_ok", "inline_fail", "skipped", "refused"}
Release == dbOwner' = IF dbOwner = "refresh" THEN "none" ELSE dbOwner

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
    /\ retired = FALSE
    /\ dispatched = FALSE
    /\ receiptErr = FALSE
    /\ verifyFailed = FALSE
    /\ lifecycle = "none"

(* upkeep.py:777-782. One writer: work fence, paused create, bind_job.      *)
(* A failed fence returns before any native effect (no jid, no cleanup).   *)
Create ==
    /\ pc = "start" /\ dbOwner = "none"
    /\ IF ~WorkFenceOk
         THEN /\ pc' = "done" /\ result' = "err_other" /\ dispatched' = dispatched
              /\ UNCHANGED <<job, slotDue>>
         ELSE /\ pc' = IF created /\ ~BrokenNoResume THEN "resume" ELSE "run"
              /\ dispatched' = (pc' = "run")
              /\ result' = result
              /\ IF created
                   THEN /\ job' = [exists |-> TRUE, enabled |-> FALSE, pending |-> TRUE]
                        /\ slotDue' = BrokenSlotDueAtCreate
                   ELSE UNCHANGED <<job, slotDue>>
    /\ UNCHANGED <<env, created, reply, err, pauseFailed, removeFailed, warned, manualRan, execs, okExecs,
                   space, userBudget, claim, userPc, userOp, dbOwner, retired, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:783-786 -> _mutate 148-150. A second writer: fence, then the  *)
(* native resume effect or refusal. A refusal rolls the writer back and    *)
(* the except branch (792-839) cleans up in a new writer.                  *)
Resume ==
    /\ pc = "resume" /\ dbOwner = "none"
    /\ IF ~WorkFenceOk
         THEN /\ err' = "pre_run" /\ job' = job /\ dbOwner' = "none"
              /\ pc' = IF FenceLost THEN "return_error" ELSE "cleanup_pause"
         ELSE \/ /\ job.exists /\ job' = [job EXCEPT !.enabled = TRUE]
                 /\ pc' = "resume_verify" /\ err' = err /\ dbOwner' = "refresh"
              \/ /\ (~job.exists \/ CronFailures) /\ job' = job
                 /\ pc' = "cleanup_pause" /\ err' = "pre_run" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, created, slotDue, reply, pauseFailed, removeFailed, result, warned, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, retired, dispatched, receiptErr,
                   verifyFailed, lifecycle>>

(* upkeep.py:151-185. The resume readback, still inside the writer.        *)
ResumeVerify ==
    /\ pc = "resume_verify" /\ dbOwner = "refresh"
    /\ \/ /\ job.exists /\ job.enabled /\ pc' = "run" /\ err' = err /\ dispatched' = TRUE
       \/ /\ (~job.exists \/ ~job.enabled \/ CronFailures)
          /\ pc' = "cleanup_pause" /\ err' = "pre_run" /\ dispatched' = dispatched
    /\ dbOwner' = "none"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, retired, receiptErr,
                   verifyFailed, lifecycle>>

(* upkeep.py:541 (no writer); assumed native _action_run eligibility/claim.*)
(* A missing job is a raised refusal (542-552); a paused one is a skipped  *)
(* success reply that continues through _run_now.                          *)
Run ==
    /\ pc = "run"
    /\ IF ~job.exists
         THEN /\ reply' = "refused" /\ pc' = "refused_fence" /\ claim' = claim
         ELSE IF ~job.enabled \/ claim # "none"
         THEN /\ reply' = "skipped" /\ pc' = "run_receipt" /\ claim' = claim
         ELSE /\ reply' = reply /\ pc' = "run_execute" /\ claim' = "manual"
    /\ UNCHANGED <<env, created, job, slotDue, err, pauseFailed, removeFailed, result, warned, manualRan,
                   execs, okExecs, space, userBudget, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:542-552. A raised run refusal rechecks the Space: a lifecycle *)
(* error replaces it; otherwise the native_refused failure is re-raised.   *)
RefusedFence ==
    /\ pc = "refused_fence"
    /\ lifecycle' = CASE space = "deleted" -> "not_found" [] space = "archived" -> "archived"
                      [] retired -> "lost" [] OTHER -> "none"
    /\ err' = IF lifecycle' = "none" THEN "refused" ELSE "post_run"
    /\ pc' = IF lifecycle' \in {"not_found", "lost"} THEN "return_error" ELSE "cleanup_pause"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed>>

(* upkeep.py:541 native execution boundary. Counts a dispatch once; only   *)
(* inline_ok establishes successful completion.                            *)
RunExecute ==
    /\ pc = "run_execute" /\ claim = "manual"
    /\ \/ /\ reply' = "inline_ok" /\ okExecs' = okExecs + 1
          /\ pc' = "run_release" /\ claim' = claim /\ slotDue' = (slotDue \/ LongRun)
       \/ /\ reply' = "inline_fail" /\ okExecs' = okExecs
          /\ pc' = "run_release" /\ claim' = claim /\ slotDue' = (slotDue \/ LongRun)
       \/ /\ reply' = "background" /\ okExecs' = okExecs
          /\ pc' = "run_reply" /\ claim' = "background" /\ slotDue' = slotDue
    /\ execs' = execs + 1 /\ manualRan' = TRUE
    /\ UNCHANGED <<env, created, job, err, pauseFailed, removeFailed, result, warned, space, userBudget,
                   userPc, userOp, dbOwner, retired, dispatched, receiptErr, verifyFailed, lifecycle>>

(* Native return boundary. The scheduler may claim after the manual claim  *)
(* clears, BEFORE the plugin sees the run reply.                           *)
RunRelease ==
    /\ pc = "run_release" /\ claim = "manual"
    /\ pc' = "run_reply" /\ claim' = "none"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:541 returns the reply to _run_now.                            *)
RunReply ==
    /\ pc = "run_reply" /\ pc' = "run_receipt"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:556-566,788,722-729. on_reply saves the reply in one writer.  *)
(* A failed write is remembered (receipt_error) and _run_now continues.    *)
RunReceipt ==
    /\ pc = "run_receipt" /\ dbOwner = "none"
    /\ receiptErr' = DbFailure /\ pc' = "run_fence"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, verifyFailed, lifecycle>>

(* upkeep.py:567-574. Read-only work fence after the run.                  *)
RunFence ==
    /\ pc = "run_fence"
    /\ lifecycle' = CASE space = "deleted" -> "not_found" [] space = "archived" -> "archived"
                      [] retired -> "lost" [] OTHER -> "none"
    /\ pc' = "run_verify"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed>>

(* upkeep.py:575-579. The dispatch verification list, AFTER the fence. A   *)
(* refusal is remembered, never treated as a run refusal.                  *)
RunVerify ==
    /\ pc = "run_verify"
    /\ verifyFailed' \in IF CronFailures THEN BOOLEAN ELSE {FALSE}
    /\ pc' = IF lifecycle \in {"not_found", "archived"} THEN "recheck_list" ELSE "run_errors"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, lifecycle>>

(* upkeep.py:584-587. Old-target observation; a failure is only cleanup.   *)
RecheckList ==
    /\ pc = "recheck_list"
    /\ \/ pc' = IF job.exists /\ lifecycle = "archived" THEN "recheck_txn" ELSE "run_errors"
       \/ /\ CronFailures /\ pc' = "run_errors"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:588 maintenance.transaction(claim): fence without archived.   *)
RecheckTxn ==
    /\ pc = "recheck_txn" /\ dbOwner = "none"
    /\ IF FenceLost THEN /\ pc' = "run_errors" /\ dbOwner' = "none"
                    ELSE /\ pc' = "recheck_pause" /\ dbOwner' = "refresh"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:580-609 then 789-791: lifecycle, receipt and verification     *)
(* errors in that order carry the run reply (post_run_check_failed or the  *)
(* lifecycle code); only then is a skipped/failed reply native_refused.    *)
(* refresh_now's except (792-839) skips cleanup for a stale claim (802).   *)
RunErrors ==
    /\ pc = "run_errors"
    /\ CASE lifecycle \in {"not_found", "lost"} -> /\ err' = "post_run" /\ pc' = "return_error"
         [] lifecycle = "archived" -> /\ err' = "post_run" /\ pc' = "cleanup_pause"
         [] receiptErr -> /\ err' = "post_run"
                          /\ pc' = IF BrokenNoPostRunCleanup THEN "return_error" ELSE "cleanup_pause"
         [] verifyFailed -> /\ err' = IF BrokenVerifyAsRefused THEN "verify_refused" ELSE "post_run"
                            /\ pc' = "cleanup_pause"
         [] reply \in {"skipped", "inline_fail"} /\ ~BrokenNoSkipCheck -> /\ err' = "refused" /\ pc' = "cleanup_pause"
         [] OTHER -> /\ err' = err /\ pc' = "consume_fence"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:842-848. One writer: work fence, then consume a created job.  *)
(* A failed fence raises with the reply and does no cleanup (864-870).     *)
ConsumeFence ==
    /\ pc = "consume_fence" /\ dbOwner = "none"
    /\ IF ~WorkFenceOk
         THEN /\ err' = "post_run" /\ pc' = "return_error" /\ dbOwner' = "none"
         ELSE /\ err' = err /\ dbOwner' = "refresh"
              /\ pc' = IF created /\ reply = "inline_ok" /\ ~BrokenNoConsume THEN "consume_pause"
                       ELSE IF created /\ reply = "background" /\ ~BrokenNoBackgroundConsume THEN "consume_pause"
                       ELSE "return_ok"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:804. Existing linked jobs are not invocation-owned cleanup.   *)
CleanupLinked ==
    /\ pc = "cleanup_pause" /\ ~created /\ pc' = "return_error"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:804-806,819-824. Cleanup writer: maintenance.transaction's    *)
(* fence (no archived check). A failed fence replaces the failure; no      *)
(* native effect.                                                          *)
CleanupTxn ==
    /\ pc = "cleanup_pause" /\ created /\ dbOwner = "none"
    /\ IF FenceLost
         THEN /\ pc' = "return_error" /\ err' = "post_run" /\ dbOwner' = "none"
         ELSE /\ pc' = "cleanup_pausing" /\ err' = err /\ dbOwner' = "refresh"
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, claim, userPc, userOp, retired,
                   dispatched, receiptErr, verifyFailed, lifecycle>>

PauseStages == {"cleanup_pausing", "consume_pause", "recheck_pause"}
PauseVerifyStage(p) == CASE p = "cleanup_pausing" -> "cleanup_pause_verify"
                           [] p = "consume_pause" -> "consume_pause_verify"
                           [] OTHER -> "recheck_pause_verify"
PauseDoneStage(p) == CASE p \in {"cleanup_pausing", "cleanup_pause_verify"} -> "cleanup_paused"
                         [] p \in {"consume_pause", "consume_pause_verify"} -> "consume_paused"
                         [] OTHER -> "recheck_paused"

(* upkeep.py:739,879,589 -> _mutate 151. The pause call may succeed/refuse.*)
NativePause ==
    /\ pc \in PauseStages /\ dbOwner = "refresh"
    /\ \/ /\ job.exists /\ job' = [job EXCEPT !.enabled = FALSE]
          /\ pauseFailed' = FALSE /\ pc' = PauseVerifyStage(pc)
       \/ /\ (~job.exists \/ CronFailures) /\ job' = job
          /\ pauseFailed' = TRUE /\ pc' = PauseDoneStage(pc)
    /\ UNCHANGED <<env, created, slotDue, reply, err, removeFailed, result, warned, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:160-185. Native pause succeeded; the readback may fail.        *)
NativePauseVerify ==
    /\ pc \in {"cleanup_pause_verify", "consume_pause_verify", "recheck_pause_verify"}
    /\ \/ /\ job.exists /\ ~job.enabled /\ pauseFailed' = FALSE
       \/ /\ (~job.exists \/ job.enabled \/ CronFailures) /\ pauseFailed' = TRUE
    /\ pc' = PauseDoneStage(pc)
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, removeFailed, result, warned, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* Cleanup: upkeep.py:742-762 (may_be_running = ~Terminal keeps the job,   *)
(* a pause failure then warns "may still be enabled"). Recheck: 588-591,   *)
(* the writer ends. Consume: 882-892.                                      *)
PauseDone ==
    /\ pc \in {"cleanup_paused", "consume_paused", "recheck_paused"}
    /\ CASE pc = "cleanup_paused" /\ Terminal ->
              /\ pc' = "cleanup_list" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
         [] pc = "cleanup_paused" ->
              /\ pc' = "return_error" /\ err' = IF pauseFailed THEN "post_run" ELSE err
              /\ warned' = (warned \/ pauseFailed) /\ dbOwner' = dbOwner
         [] pc = "recheck_paused" -> /\ pc' = "run_errors" /\ err' = err /\ warned' = warned /\ dbOwner' = "none"
         [] pc = "consume_paused" /\ reply = "background" /\ pauseFailed ->
              /\ pc' = "return_error" /\ err' = "post_run" /\ warned' = TRUE /\ dbOwner' = dbOwner
         [] pc = "consume_paused" /\ reply = "background" /\ ~pauseFailed ->
              /\ pc' = "return_ok" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
         [] OTHER -> /\ pc' = "consume_remove" /\ err' = err /\ warned' = warned /\ dbOwner' = dbOwner
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, retired, dispatched, receiptErr,
                   verifyFailed, lifecycle>>

(* upkeep.py:746. The terminal cleanup list can independently fail.        *)
CleanupList ==
    /\ pc = "cleanup_list"
    /\ \/ /\ job.exists /\ pc' = "cleanup_remove" /\ err' = err /\ warned' = warned
       \/ /\ ~job.exists /\ pc' = "return_error" /\ err' = err /\ warned' = warned
       \/ /\ CronFailures /\ pc' = "return_error" /\ err' = "post_run" /\ warned' = (warned \/ pauseFailed)
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

RemoveVerifyStage(p) == IF p = "cleanup_remove" THEN "cleanup_remove_verify" ELSE "consume_remove_verify"
RemoveDoneStage(p) == IF p = "cleanup_remove_verify" THEN "cleanup_removed" ELSE "consume_removed"

(* upkeep.py:747,891 -> _mutate 151-170. Even a refused remove is followed *)
(* by a readback; absence reconciles an already-absent job.                *)
NativeRemove ==
    /\ pc \in {"cleanup_remove", "consume_remove"}
    /\ \/ job' = NoJob
       \/ /\ CronFailures /\ job' = job
    /\ pc' = RemoveVerifyStage(pc)
    /\ UNCHANGED <<env, created, slotDue, reply, err, pauseFailed, removeFailed, result, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

NativeRemoveVerify ==
    /\ pc \in {"cleanup_remove_verify", "consume_remove_verify"}
    /\ \/ /\ ~job.exists /\ removeFailed' = FALSE
       \/ /\ (job.exists \/ CronFailures) /\ removeFailed' = TRUE
    /\ pc' = RemoveDoneStage(pc)
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, result, warned, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:748-762 (cron_cleanup_failed replaces the reason) and 890-900.*)
RemoveDone ==
    /\ pc \in {"cleanup_removed", "consume_removed"}
    /\ IF pc = "cleanup_removed"
         THEN /\ pc' = "return_error"
              /\ err' = IF removeFailed THEN "post_run" ELSE err
              /\ warned' = (warned \/ (removeFailed /\ pauseFailed))
         ELSE /\ pc' = IF removeFailed /\ pauseFailed THEN "return_error" ELSE "return_ok"
              /\ err' = IF removeFailed /\ pauseFailed THEN "post_run" ELSE err
              /\ warned' = (warned \/ (removeFailed /\ pauseFailed))
    /\ UNCHANGED <<env, created, job, slotDue, reply, pauseFailed, removeFailed, result, manualRan, execs,
                   okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:840-871. result=ok is dispatch acceptance, not completion.    *)
ReturnOk ==
    /\ pc = "return_ok" /\ pc' = "done" /\ result' = "ok" /\ Release
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:789-791 native_refused vs every other error. verify_refused   *)
(* exists only under BrokenVerifyAsRefused (the pre-b57f3cc F1 mapping).   *)
ReturnError ==
    /\ pc = "return_error" /\ pc' = "done" /\ Release
    /\ result' = CASE err = "refused" -> "err_refused"
                    [] err = "verify_refused" -> "err_verify_refused"
                    [] OTHER -> "err_other"
    /\ UNCHANGED <<env, created, job, slotDue, reply, err, pauseFailed, removeFailed, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* upkeep.py:28 ONE_SHOT_SLOT. Bounded clock.                              *)
ClockReachesSlot ==
    /\ ~slotDue /\ job.exists /\ job.pending /\ pc = "done" /\ slotDue' = TRUE
    /\ UNCHANGED <<env, pc, created, job, reply, err, pauseFailed, removeFailed, result, warned, manualRan,
                   execs, okExecs, space, userBudget, claim, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* Native assumption. Only fresh once jobs.                                *)
SchedulerClaim ==
    /\ created /\ job.exists /\ job.enabled /\ job.pending /\ slotDue /\ claim = "none"
    /\ claim' = "scheduler"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* Already claimed work may run despite a pause; cancellation on remove is *)
(* abstracted conservatively as may still run.                             *)
SchedulerExecute ==
    /\ claim = "scheduler" /\ claim' = "scheduler_settle" /\ execs' = execs + 1
    /\ okExecs' \in {okExecs, okExecs + 1}
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, space, userBudget, userPc, userOp, dbOwner, retired, dispatched, receiptErr,
                   verifyFailed, lifecycle>>

(* Scheduled completion spends repeat=1; a removed record is not recreated.*)
SchedulerRetire ==
    /\ claim = "scheduler_settle" /\ claim' = "none"
    /\ job' = IF job.exists THEN [exists |-> TRUE, enabled |-> FALSE, pending |-> FALSE] ELSE job
    /\ UNCHANGED <<env, pc, created, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

BackgroundRelease ==
    /\ claim = "background" /\ claim' = "none"
    /\ UNCHANGED <<env, pc, created, job, slotDue, reply, err, pauseFailed, removeFailed, result, warned,
                   manualRan, execs, okExecs, space, userBudget, userPc, userOp, dbOwner, retired, dispatched,
                   receiptErr, verifyFailed, lifecycle>>

(* maintenance.py:209-253 + transaction; upkeep.py:683-711 (pause/remove), *)
(* 903-914 (archive), 917-932 (delete). One writer for the whole slice.    *)
UserStart ==
    /\ ~NoUserAction
    /\ userBudget > 0 /\ dbOwner = "none"
    /\ userOp' \in {"pause", "remove", "archive", "delete"}
    /\ space # "deleted" /\ (userOp' # "archive" \/ space = "active")
    /\ userBudget' = userBudget - 1 /\ userPc' = "list" /\ dbOwner' = "user"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, space, claim, retired>>

UserRemoves == userOp \in {"remove", "delete"}

(* upkeep.py:689,907,922. Owned jobs include the claimed one (_owned_jobs).*)
UserList ==
    /\ userPc = "list" /\ dbOwner = "user"
    /\ \/ userPc' = IF job.exists THEN "mutate" ELSE "final_list"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, space, userBudget, claim,
                   userOp, dbOwner, retired>>

(* upkeep.py:702,909,926 -> _mutate. Abort cannot roll back this effect.   *)
UserMutate ==
    /\ userPc = "mutate" /\ dbOwner = "user"
    /\ \/ /\ (job.exists \/ UserRemoves)
          /\ job' = IF UserRemoves THEN NoJob ELSE [job EXCEPT !.enabled = FALSE]
          /\ userPc' = "verify"
       \/ /\ (~job.exists \/ CronFailures) /\ job' = job
          /\ userPc' = IF UserRemoves THEN "verify" ELSE "abort"
    /\ UNCHANGED <<env, refreshVars, slotDue, manualRan, execs, okExecs, space, userBudget, claim,
                   userOp, dbOwner, retired>>

UserValid == IF UserRemoves THEN ~job.exists ELSE job.exists /\ ~job.enabled

UserVerify ==
    /\ userPc = "verify" /\ dbOwner = "user"
    /\ \/ userPc' = IF UserValid THEN "final_list" ELSE "abort"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, space, userBudget, claim,
                   userOp, dbOwner, retired>>

(* upkeep.py:703-706,910-911,927-928.                                      *)
UserFinalList ==
    /\ userPc = "final_list" /\ dbOwner = "user"
    /\ \/ userPc' = IF ~job.exists \/ (~UserRemoves /\ ~job.enabled) THEN "commit" ELSE "abort"
       \/ /\ CronFailures /\ userPc' = "abort"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, space, userBudget, claim,
                   userOp, dbOwner, retired>>

(* projects.py:588-589,616; maintenance.py:504-514 (remove/delete retire   *)
(* the refresh claim and bump link_generation in the same commit).         *)
UserCommit ==
    /\ userPc = "commit" /\ dbOwner = "user"
    /\ space' = CASE userOp = "archive" -> "archived"
                    [] userOp = "delete" -> "deleted"
                    [] OTHER -> space
    /\ retired' = (retired \/ UserRemoves)
    /\ userPc' = "done" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, userBudget, claim, userOp>>

UserAbort ==
    /\ userPc = "abort" /\ dbOwner = "user"
    /\ userPc' = "done" /\ dbOwner' = "none"
    /\ UNCHANGED <<env, refreshVars, job, slotDue, manualRan, execs, okExecs, space, userBudget, claim,
                   userOp, retired>>

Finished ==
    /\ pc = "done" /\ claim = "none" /\ dbOwner = "none"
    /\ ~(created /\ job.exists /\ job.enabled /\ job.pending)
    /\ UNCHANGED vars

Next ==
    \/ Create \/ Resume \/ ResumeVerify
    \/ Run \/ RefusedFence \/ RunExecute \/ RunRelease \/ RunReply
    \/ RunReceipt \/ RunFence \/ RunVerify \/ RecheckList \/ RecheckTxn \/ RunErrors
    \/ ConsumeFence \/ CleanupLinked \/ CleanupTxn
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

(* Fresh invocation-owned once jobs only; linked recurring jobs excluded.  *)
AtMostOnce == (created /\ ~warned) => execs <= 1

(* ok means evidenced dispatch, not successful background completion.      *)
NoSuccessForSkippedRun == result = "ok" => (manualRan /\ reply \in {"inline_ok", "background"})

(* okExecs counts evidenced successful completions only.                   *)
NoFalseRefusal == (result = "err_refused" /\ ~warned) => okExecs = 0
(* F1, fixed at b57f3cc/f56321d: a refused post-run check is not a refusal.*)
NoRefusalAfterSuccessfulRun == (result = "err_verify_refused" /\ ~warned) => okExecs = 0
=============================================================================
