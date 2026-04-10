# Indian Income Tax Calculator

Converts a filled `Script_input.json` into a computed `Script_output.json` by applying Indian income tax rules — covering salary income, capital gains, deductions, and tax computation.

## Usage

```bash
python3 tax_calculator.py <input.json> <output.json>
```

Example:
```bash
python3 tax_calculator.py Script_input.json my_output.json
```

## Input / Output

| File | Purpose |
|------|---------|
| `Script_input.json` | Template — fill this with your financial details |
| `Script_output.json` | Template — shows the structure of computed output |
| `Input_to_script_Template.json` | Reference: IT-portal-level section values (what you'd enter on the portal) |
| `Output_of_script_template.json` | Reference: raw income/expense breakdown format |

## Running Tests

```bash
python3 tests/run_tests.py
```

Six test cases covering: all-zero input, HRA exemption, STCG/LTCG classification, 80C cap, 80G donations, and Section 87A rebate.

## Updating for a New Financial Year

Tax slabs, rebate thresholds, and rate constants are defined at the top of `tax_calculator.py`:

```python
NEW_REGIME_SLABS      = [...]   # FY slab rates
REBATE_87A_THRESHOLD  = 1_200_000
REBATE_87A_MAX        = 60_000
LTCG_112A_EXEMPT      = 1_25_000
```

Update these to switch financial year or regime assumptions without touching calculation logic.

## Version History

See `CHANGELOG.md` for what each version computes and what is currently a placeholder.
