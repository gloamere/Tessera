# Gloamere Workflows provenance

This file separates Gloamere-authored workflow contracts from the isolated
third-party UI data and helper core shipped in the GitHub beta. Audit date:
2026-07-23.

## Original workflow contracts

`gloamere-visual-review`, `gloamere-knowledge-capture`, and
`gloamere-product-decision` were rewritten from Gloamere's product boundaries,
failure categories, and output contracts. They do not retain their predecessor
text. The comparison below uses lowercase UTF-8 text with whitespace removed;
the Jaccard score is calculated over all 12-character windows.

| Current Skill | Pre-4.0 predecessor SHA-256 | Current SHA-256 | Sequence ratio | 12-character Jaccard | Longest shared block |
| --- | --- | --- | ---: | ---: | ---: |
| `gloamere-visual-review` | `035bd3dbfe6031b968026dda0227fc116e488b30c3a17bb298831c7b478b2aa2` | `11b8c82df657f925401eed89f2a4e24a572df705441ed29198059d8e7bb8409f` | 0.1094 | 0.0013 | 13 chars |
| `gloamere-knowledge-capture` | `b2bcfaa832ed625219489849ce65d4287a3840dbcbc3e336b039fd485b821573` | `b8432c8bdad9a7850aeb8928648dc719b92556a64c2663fce8d1a4f6fa73e4c3` | 0.0907 | 0.0018 | 14 chars |
| `gloamere-product-decision` | `dac544d6d6d8aecd6c80db6f8230c32b5949f1fd92f04df39075cbd7b710ada3` | `d102eb99df24cee6c19d3174e4b940e3f51669c7d2c61304f0bf8c131184520a` | 0.3979 | 0.0159 | 20 chars |

The visual-review predecessor cited
[`Leonxlnx/taste-skill`](https://github.com/Leonxlnx/taste-skill) as an
inspiration. Against all 13 upstream `SKILL.md` files at commit
[`98565e65`](https://github.com/Leonxlnx/taste-skill/commit/98565e65bc3274ddf6eb0838734341714057178b),
the current Gloamere file's maximum 12-character Jaccard score is 0.0003 and
its longest shared block is 12 normalized characters.

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

## Isolated UI vendor core

The GitHub beta of `gloamere-ui-system` contains a pinned MIT vendor core from
[`nextlevelbuilder/ui-ux-pro-max-skill`](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/f8ac5e1266dba8354ea96e19994d9f4345e7ec31).
Its exact file boundary and the single host-neutral documentation adjustment
are recorded in
[`skills/gloamere-ui-system/references/UPSTREAM.md`](skills/gloamere-ui-system/references/UPSTREAM.md).
The full copyright and license text is preserved in
[`THIRD_PARTY_NOTICES/next-level-builder-MIT.txt`](THIRD_PARTY_NOTICES/next-level-builder-MIT.txt).

The Gloamere Skill ID, routing boundary, orchestration, output contract, and
evaluation suite are not vendor material. Official-directory GA remains gated
on replacing the vendor core with Gloamere-owned taxonomy, data, scripts, and
rules, then rerunning all identity, routing, and quality evaluations at the new
SHA.
