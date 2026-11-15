# Design plan — making this site look like W3Schools

One page. What W3Schools actually does (measured), what we adopt, what we refuse,
and why. Everything here is a decision with a reason, not a mood.

## What I measured

Read from `w3schools.com/lib/w3schools31.css` (W3.CSS 4.15) and from two
independent colour studies of the live site:

| Fact | Value |
|---|---|
| Body type | Verdana, sans-serif, **15px**, line-height 1.5 |
| Heading type | `"Segoe UI", Arial, sans-serif`, **weight 400**, h1 36 / h2 30 / h3 24 / h4 20 |
| Brand green | `#04AA6D` (Deep Sea Green), hover `#059862` |
| Dark surface | `#282A35` (Cool Charcoal); dark-mode grey `#38444D` |
| Code / panel grey | `#E7E9EB`, header strip `#F1F1F1` |
| Pale green | `#D9EEE1` |
| Borders | `#DDDDDD` |
| Text | `#0F172A` headings, `#64748B` muted |
| Cards | `border-radius: 5px` (`w3-round`), flat — no drop shadow |
| Primary button | green pill: `border-radius: 25px`, 18px, white on green |
| Secondary button | white pill, 25px radius, hover fills `#E7E9EB` |
| Editor chrome | `#F1F1F1` bar with three dots (`#ED594A`, `#FDD800`, `#5AC05A`) |

The look is not "dark and sleek". It is **light, green, flat and roomy**: white
page, grey code panels with black text, pill buttons, 5px corners, and a green
left-bar on whatever you are reading.

## What we adopt

1. **The palette, exactly** — `#04AA6D` accent, `#282A35` dark surface,
   `#E7E9EB` code panel, `#D9EEE1` pale green, `#DDDDDD` borders, `#0F172A` text.
2. **Light code panels.** Our code was dark in both themes; W3Schools is the
   opposite, and the light grey panel with black mono text is the single most
   recognisable thing about the site. Adopted.
3. **Pill buttons.** Run becomes a green pill, Copy and Reset white pills, with
   `#059862` / `#E7E9EB` hovers.
4. **5px corners, no drop shadows.** Flat cards with a 1px `#DDDDDD` border.
5. **The editor strip.** Three dots and a `#F1F1F1` bar above each code block.
6. **Green left-bar on the current lesson**, and a light grey sidebar.
7. **Segoe UI headings at weight 400**, sized 34 / 26 / 20.
8. **Generous whitespace**: 16px body leading, 24px card padding, 8px rhythm.

## What we refuse, and why

| W3Schools does | We do | Reason |
|---|---|---|
| `#04AA6D` on white for links | `#047857` (5.48:1) | The exact green is 3.01:1 — fine for 18px button text, a fail for 16px body text. Same hue, darker step. |
| White on `#04AA6D` buttons at any size | White on `#047857` for text-bearing fills; `#04AA6D` only where the label is ≥18px or the element carries no text | 3.01:1 fails AA at 16px. |
| Verdana 15px body | Segoe UI / Verdana stack at 16px, line-height 1.55 | 15px Verdana is cramped for 300-word prose. One step up, same family feel. |
| No visible focus ring | 3px `#047857` ring with a white halo | Their site relies on browser default; ours must survive keyboard use. |
| Fixed 5px radius everywhere | 5px cards, 25px pills, 6px inline code | Their buttons are pills and their cards are not; that contrast is the design. |

## The token set

```
--accent        #04AA6D   brand: bars, borders, dots, large labels
--accent-strong #047857   text and filled buttons (AA)
--accent-hover  #059862
--accent-soft   #D9EEE1
--bg            #FFFFFF   --surface #F1F1F1   --surface-2 #E7E9EB
--border        #DDDDDD   --text #0F172A      --muted #64748B
--code-bg       #E7E9EB   --code-text #000000 --code-header #F1F1F1
dark: --bg #282A35  --surface #1F2229  --surface-2 #38444D
      --text #FFFFFF --muted #B9C0CC  --code-bg #1B1E26
```

## How I will know it worked

- Screenshot parity check: light page, grey code panel, green pill, 5px cards.
- `#04AA6D` appears only on non-text or large-text surfaces; every text pair
  ≥4.5:1 in both themes.
- No dark code panel in the light theme.
- 375px: no horizontal scroll; the drawer still opens.
- The runner still executes: lesson 1.1 → `verdict: block`.
