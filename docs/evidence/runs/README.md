# Committed run receipts

Raw harness output copied from the external build evidence directory (`living-spaces-r1/evidence/`) so each claim in `R1-STATUS.md` survives review without that directory. Failed and vacuous attempts are kept beside the passing run and are not counted.

- `r1-09-repair/` is `harness/qualify_repair.py` at `9716769`. `repair.json` and `run-2.log` are the 15/15 run. `repair-run-1*` is the gateway WebSocket 403 attempt. One traceback path is redacted to `<hermes-runtime-venv>`.
- `r1-05-authority/` is `harness/qualify_authority.py` at the commit in `run-6.sha` (`8724804`). `authority.json` and `run-6.log` are the 22/22 run. Attempts 1 to 5 are the retained harness corrections.
- `validate-8724804/` is `hermes plugins validate --install-deps` on a clean export of `872480426c70fb7cfac1eda3d0837809a66e6955` (`sha`, `exit`, `raw.log`), recorded by `6793ae8`.
