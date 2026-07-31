# Gloamere Workflows provenance

This file records the clean-room and repository provenance of the three
Gloamere-authored workflows included in the public skills-only package. Audit
date: 2026-07-31.

## Original workflow contracts

`gloamere-visual-review`, `gloamere-knowledge-capture`, and
`gloamere-product-decision` were rewritten from Gloamere's product boundaries,
failure categories, and output contracts. They do not retain their predecessor
text. The comparison below uses lowercase UTF-8 text with whitespace removed;
the Jaccard score is calculated over all 12-character windows.

| Current Skill | Pre-4.0 predecessor SHA-256 | Current SHA-256 | Sequence ratio | 12-character Jaccard | Longest shared block |
| --- | --- | --- | ---: | ---: | ---: |
| `gloamere-visual-review` | `035bd3dbfe6031b968026dda0227fc116e488b30c3a17bb298831c7b478b2aa2` | `166787e6fd79b858548a07b0c0238157331fc1d5962b009324ecb44d515a9264` | 0.1370 | 0.0011 | 13 chars |
| `gloamere-knowledge-capture` | `b2bcfaa832ed625219489849ce65d4287a3840dbcbc3e336b039fd485b821573` | `d892d32e81c9abad95d6885d438454312b9f82a5a96d7b9cbf7d51886104d864` | 0.1383 | 0.0015 | 14 chars |
| `gloamere-product-decision` | `dac544d6d6d8aecd6c80db6f8230c32b5949f1fd92f04df39075cbd7b710ada3` | `30a4692b50af16a50bd51f8ba17efd10a0b190f2f7714beb94dc38d8261749b3` | 0.3661 | 0.0141 | 20 chars |

The visual-review predecessor cited
[`Leonxlnx/taste-skill`](https://github.com/Leonxlnx/taste-skill) as an
inspiration. Against all 13 upstream `SKILL.md` files at commit
[`98565e65`](https://github.com/Leonxlnx/taste-skill/commit/98565e65bc3274ddf6eb0838734341714057178b),
the current Gloamere file's maximum 12-character Jaccard score is 0.0003 and
its longest shared block is 18 normalized characters.

The knowledge predecessor cited
[`kepano/obsidian-skills`](https://github.com/kepano/obsidian-skills) as an
inspiration. Against all five upstream `SKILL.md` files at commit
[`a1dc48e6`](https://github.com/kepano/obsidian-skills/commit/a1dc48e68138490d522c04cbf5822214c6eb1202),
the current Gloamere file's maximum 12-character Jaccard score is 0.0011 and
its longest shared block is 13 normalized characters.

Both cited repositories reported MIT licenses at audit time. No upstream file
from either repository is included in these three current Skill directories.
The product-decision predecessor was authored in this repository in commit
`c19f22f` under the repository MIT license.

These metrics are an engineering originality screen, not a legal opinion.
Changing any listed Skill invalidates its current hash and requires the audit
and current-SHA evaluations to be rerun.

## Incubated UI candidate

`gloamere-ui-system` and its pinned MIT vendor core are isolated under
[`experiments/workflows/gloamere-ui-system`](../../experiments/workflows/gloamere-ui-system).
They are not part of this plugin, the Git marketplace release, any future
official-directory submission, or either release archive. The candidate can
return only after its taxonomy, data, scripts, and rules are replaced by
Gloamere-owned material and its identity, routing, and quality evidence are
rerun at the replacement SHA.
