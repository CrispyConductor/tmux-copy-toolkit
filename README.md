# Tmux Rapid Copy Toolkit

This tmux plugin is intended to allow copying on-screen data as efficiently and
in as few keystrokes as possible.  It is inspired by several other tmux plugins
including [tmux-jump](https://github.com/schasse/tmux-jump), [tmux-fingers](https://github.com/Morantron/tmux-fingers),
[tmux-open](https://github.com/tmux-plugins/tmux-open), and other similar ones.
This plugin combines, improves, and adds functionality on top of a common interface,
with particular attention paid to stability and reliability with respect to wrapped
lines, panes, zooming, etc.

* [Tmux Rapid Copy Toolkit](#tmux-rapid-copy-toolkit)
   * [Features](#features)
      * [easymotion](#easymotion)
      * [easycopy](#easycopy)
      * [quickcopy](#quickcopy)
      * [quickopen](#quickopen)
   * [Requirements](#requirements)
   * [Installation](#installation)
      * [Manual Install](#manual-install)
   * [Keybinds](#keybinds)
   * [Options](#options)
      * [quickcopy/quickopen matches](#quickcopyquickopen-matches)
         * [Custom quickcopy example](#custom-quickcopy-example)


## Features

There are 4 major modes/features:

### easymotion

This is a reimplementation of the classic vim-style easymotion movement.  It allows
rapid seeking to anywhere in copy-mode in just a few keystrokes (typically 3 or 4).

In tmux copy-mode, hit
the easymotion key (by default `s`), then enter the character at the desired
seek destination.  Each instance of that character will then be highlighted
and replaced with one or more letters.  Enter the letter(s) corresponding
to the desired seek destination to seek there.  The j, k, and n line-based
actions are also supported.

This mode has several variants that can be configured using options.

### easycopy

This is effectively two easymotion movements in series to set the start and end
positions of a block of text to copy.  This can be used outside of copy-mode.
With default keybinds, it allows copying nearly any arbitrary block of text
on screen in 8 keystrokes or less (including prefix).

To use, hit `Ctrl-b` `S` to activate easycopy mode.  Then enter the character
at the start of the region to copy, and key in the corresponding label
that appears.  Immediately after, enter the character at the end (inclusive)
of the region to copy, then the corresponding label.  The block will
then flash to confirm and will be copied.

### quickcopy

This mode allows copying some of the most common elements of text in even
fewer keystrokes; as few as 3 (including prefix) for very commonly-copied
things like URLs.
A set of patterns for commonly-copied elements such as
paths, filenames, URLs, etc. is configured in tmux.conf (with a reasonable
set of defaults) and these are used to select copyable regions.

To use, hit `Ctrl-b` `Q` to active quickcopy mode.  All matched elements on
screen will be highlighted with associated labels.  Key in the label to
copy the region of text.  Shorter labels are assigned to the higher-priority
matches.  If there are overlapping matches (there usually are), matches
are displayed sequentially in batches - press `n` to advance to the next
batch.  Batches are arranged by configured priority, but also optimized
to fit as many matches on-screen as possible in a batch.

### quickopen

This mode allows quickly opening URLs in a browser or absolute paths with their
respective applications.

It is activated with `Ctrl-b` `P` and behaves identially to quickcopy mode,
except that only openable things are highlighted.  Selecting one invokes
`xdg-open` (on Linux) or `open` (on Mac).  It also includes a mechanism
to import X environment variables from external source to ensure the command
can reach X.

## Requirements

- python3
- bash

## Installation

Using [tmux plugin manager](https://github.com/tmux-plugins/tpm), add the following
to your tmux.conf:

```
set -g @plugin 'CrispyConductor/tmux-copy-toolkit'
```

Then reload tmux with `Ctrl-b` `:source ~/.tmux.conf` and install TPM plugins
with `Ctrl-b` `I`.

### Manual Install

To install without TPM:

```
git clone https://github.com/CrispyConductor/tmux-copy-toolkit/ ~/path/to/somewhere/
```

Then add to `tmux.conf`:

```
run-shell ~/path/to/somewhere/copytk.tmux
```

## Keybinds

This table specifies the default keybinds.  Additional keybinds can be added to
tmux.conf.  The defaults can be suppressed by adding this to tmux.conf:

```
set -g @copytk-no-default-binds on
```

You can find the commands corresponding to each binding in [copytk.tmux](copytk.tmux).

Mode | Action | Default Key
---- | ------ | -----------
copy | easymotion seek | `s`
copy | easymotion seek 2-char | `S` `S`
copy | easymotion "j" action (lines below cursor) | `S` `j`
copy | easymotion "k" action (lines above cursor) | `S` `k`
copy | easymotion lines action (all lines) | `S` `n`
any | easycopy | `<Prefix>` `S`
any | quickcopy | `<Prefix>` `Q`
any | quickopen | `<Prefix>` `P`

## Options

These options can be configured in your tmux.conf like:

```
set -g @copytk-copy-command "VALUE"
```

Option | Default | Description
------ | ------- | -----------
`@copytk-copy-command` | `tmux load-buffer -` | Command to run to copy data.  The command is run in a shell and data is piped to its stdin.
`@copytk-label-chars` | `asdghklqwertyuiopzxcvbnmfj;` | Characters to use for labels.
`@copytk-cancel-key` | `Escape Enter ^C` | Key(s) to use to cancel out of a mode.  These are curses-style key names (with the exception of a few that are mapped).
`@copytk-flash-time` | `0.5` | Seconds to flash copied text on screen.
`@copytk-preflash-time` | `0.05` | Seconds to blank screen before flash.
`@copytk-case-sensitive-search` | `upper` | Case sensitivity for easymotion search char.  on=case sensitive; off=not case sensitive; upper=case sensitive only for uppercase search char
`@copytk-min-match-spacing` | `2` | Minimum distance between easymotion search matches.
`@copytk-quickcopy-match-*` | | quickcopy patterns; see below
`@copytk-quickopen-match-*` | | 
`@copytk-quickcopy-next-batch-char` | `n` | Key to assign to switching to next batch in quickcopy mode.
`@copytk-quickopen-next-batch-char` | `n` | 
`@copytk-quickcopy-min-match-len` | `4` | Minimum length of matching blocks for quickcopy.
`@copytk-quickopen-min-match-len` | `4` | 
`@copytk-quickcopy-pack-tiers` | `on` | Whether to allow mixing match tiers in the same batch to pack more in.
`@copytk-flash-only-one` | `on` | In quickcopy mode, if there is more than one instance of the copied text on-screen, this is whether to flash all occurrences of the text or just one.
`@copytk-quickopen-env-file` | `~/.tmux-copytk-env` | Path to a file containing newlike-separated `KEY=VALUE` environment variables.  These are added to the environment for running the open command.  Generation of this file can be automated in your shellrc.
`@copytk-quickopen-open-command` | `xdg-open` on Linux, `open` on Mac | Command to run to open selected blocks in quickopen.  The selected text is passed as an argument.
`@copytk-color-highlight` | `green:yellow` | The color to use for highlighted matches, in the form `foreground`:`background`.  Valid names are: `none`, `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`
`@copytk-color-labelchar` | `red:none` | The color to use for the first/active label character.
`@copytk-color-labelchar2` | `yellow:none` | The color to use for the second and subsequent label characters.
`@copytk-color-message` | `red:none` | The color to use for the status message.

### quickcopy/quickopen matches

Match patterns for quickcopy and quickopen can be configured as well.  Patterns for the 2 modes are tracked separately; all quickcopy match options have quickopen equivalents.

Patterns are divided into numbered tiers starting at 0.  Tiers define the priorities for matches to be displayed when there are
overlaps.  Organizing patterns into tiers can be important for quickly finding the desired match.  Lower-numbered
tiers are higher priority.

Patterns are entered as options in the form `@copytk-quickcopy-match-<TierNum>-<PatternNum>` .  The value is either
a regular expression or a built-in pattern key.  Tier numbers start at 0 and must be contiguous.
Pattern numbers also start as 0 (for each tier) and also must be contiguous.

Any duplicate matches (within or across tiers) are removed; only the highest priority one is kept.

For an example of what this looks like, take a look at the defaults in [copytk.tmux](copytk.tmux).

To suppress the default patterns and completely redefine your own:

```
set -g @copytk-no-default-matches on
```

The built-in pattern keys that can be used in place of a regex are:

- `urls` - Match a subset of URLs that are likely to occur in a delimited terminal environment.
- `abspaths` - Match absolute paths, either UNIX or Windows style.
- `paths` - Match all paths, absolute and relative.
- `filenames` - Match isolated filenames that occur without a path separator.
- `lines` - Match each individual whole line.

In addition to these, the defaults include patterns for:

- IP addresses
- Commands entered after a $ prompt
- Numbers longer than a threshold
- Quote-enclosed strings

#### Custom quickcopy example

As an example, here's how one might define a simple quickcopy regex to match basic SQL-query-like things:

```
set -g @copytk-quickcopy-match-0-1 '(SELECT|INSERT) .+;'
```

This adds the regex as a tier 0 (high priority) match.  It's added as index 1 in tier 0 because quickcopy-match-0-0 is already used by the defaults (but can be changed).




