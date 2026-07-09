# AnkiVoice Core

A personal, non-commercial study utility for Anki users: deck conversion, vocabulary processing, APKG analysis, quiz support, local audio management, and optional FFmpeg-based audio conversion.

## Overview

AnkiVoice Core is an unofficial utility tool for Anki users.

It can:

* Convert Anki `.apkg` files into `.csv` files
* Convert `.txt` files exported from Anki into `.csv` files
* Generate plain text vocabulary lists
* Analyze APKG review history and generate study reports
* Run APKG-based vocabulary quizzes
* Organize local audio files for personal language-learning workflows
* Convert supported audio formats using FFmpeg (optional)

This software is intended only for personal, educational, and non-commercial study use.

AnkiVoice Core is not affiliated with, endorsed by, sponsored by, authorized by, or officially connected to Anki, AnkiWeb, or any other third-party service provider.

## Requirements

```txt
requests>=2.32.0
tqdm>=4.67.0
zstandard>=0.23.0
cryptography>=45.0.0
```

## Installation

```bash
pip install -r requirements.txt
python AnkiVoice.py
```

## Additional Feature and Update Information

The following section supplements the original project description above.  
The existing project purpose, licensing position, third-party rights notice, usage restrictions, and disclaimer remain unchanged.

AnkiVoice Core v1.5.0 expands the program with additional study-support features, file-management improvements, and optional FFmpeg-based audio conversion support. These updates are intended to make the tool more useful for personal Anki workflows while keeping the project within its original scope: a local, unofficial, personal, educational, and non-commercial study utility.

### v1.5.0 Update Summary

AnkiVoice Core v1.5.0 includes improvements across APKG analysis, quiz support, audio file organization, filename cleanup, extension handling, and audio format conversion.

The main update areas are:

* APKG review history analysis and improved study reports
* APKG Word Quiz support
* Expanded Audio File Manager functions
* Filename cleanup and extension-management improvements
* Optional FFmpeg-based audio format conversion
* Automatic FFmpeg download-page guidance when FFmpeg is not detected
* Safer and more predictable FFmpeg detection behavior
* Improved menu wording, confirmation messages, saved-file notices, and overall screen readability

### APKG Analysis Report

AnkiVoice Core now includes APKG review history analysis.

This feature reads supported APKG data locally and generates a study report based on review history and related learning indicators. It is designed to help users identify vocabulary cards that may require additional review, cards that repeatedly receive incorrect answers, and cards whose long-term retention may still be weak.

The APKG analysis report has been revised for better readability. Summary values, classification criteria, explanatory sections, and word examples are presented with clearer spacing and structure. The analysis completion screen has also been adjusted so that the program shows the saved report location instead of repeatedly printing the full report content to the console.

This feature is only a personal study aid. It does not replace Anki, AnkiWeb, FSRS, or any official scheduling or review system.

### APKG Word Quiz

AnkiVoice Core now supports an APKG-based vocabulary quiz workflow.

Users can select an APKG file, choose the field used for quiz questions, choose the field used for meanings or answers, and run a short multiple-choice vocabulary quiz. The quiz feature is intended for quick personal review before or after regular Anki study.

The quiz workflow does not modify the original APKG file and does not upload quiz data to any external service.

### Audio File Manager Improvements

The Audio File Manager provides local file-organization tools for Anki media workflows.

Recent versions support moving local audio files into Anki's `collection.media` folder, using a saved `collection.media` path, optionally removing remaining files after a successful move, replacing underscores in filenames with half-width spaces, and managing filename and extension handling more consistently.

Extension-related menus and guide messages have also been refined. The program now more clearly separates filename cleanup, extension correction, and actual audio format conversion so that users can understand what each operation does before running it.

These features are intended to reduce repetitive manual work during personal vocabulary-deck preparation.

### FFmpeg-Based Audio Conversion

AnkiVoice Core now supports optional audio format conversion through FFmpeg.

This feature can convert supported audio files into formats commonly used in Anki media workflows, including MP3 and other supported audio formats. It is intended for users who need to normalize or prepare audio files for personal Anki decks.

FFmpeg is **not included** with AnkiVoice Core.

Users who want to use audio conversion must prepare FFmpeg separately. If FFmpeg is not detected, AnkiVoice Core opens the official FFmpeg download page in the user's default browser.

Official FFmpeg download page:

https://www.ffmpeg.org/download.html

This browser guidance is provided only for user convenience. AnkiVoice Core is not affiliated with FFmpeg, does not distribute FFmpeg, and does not grant any license to FFmpeg. Users are responsible for obtaining FFmpeg from an appropriate source and complying with the applicable FFmpeg license terms.

### FFmpeg Compatibility and Detection Scope

FFmpeg-based conversion depends on the user's local PC environment, the available FFmpeg build, and the codecs supported by that FFmpeg installation.

The presence of the audio conversion menu does not guarantee that every audio file, codec, container format, or damaged media file can be converted successfully. Actual conversion results may vary depending on input file condition, FFmpeg availability, operating system behavior, and codec support.

To make FFmpeg behavior more predictable, AnkiVoice Core intentionally restricts FFmpeg detection.

AnkiVoice Core does not search the whole computer, parent folders, system PATH, previously saved external FFmpeg paths, or arbitrary recursive locations. FFmpeg detection is limited to the local `ffmpeg` directory associated with the audio converter module.

Allowed detection locations include:

* `ffmpeg/ffmpeg.exe`
* `ffmpeg/bin/ffmpeg.exe`
* `ffmpeg/<child-folder>/ffmpeg.exe`
* `ffmpeg/<child-folder>/bin/ffmpeg.exe`
* ZIP files directly inside the local `ffmpeg` directory
* ZIP files directly inside child folders under the local `ffmpeg` directory

This restriction prevents AnkiVoice Core from accidentally detecting or using an unrelated FFmpeg installation elsewhere on the user's PC.

### File Operation and Backup Notice

Some AnkiVoice Core features may move files, rename files, change extensions, create converted audio files, or process many files at once.

Before using file movement, filename cleanup, extension correction, or audio conversion features, users should back up important files. Users are responsible for checking selected folders, selected files, output paths, overwrite settings, deletion options, and confirmation prompts before running any batch operation.

The developer does not guarantee that every APKG file, Anki profile, audio file, local folder structure, FFmpeg build, codec, or operating system environment will behave identically.

## License

Copyright (c) 2026 Lutte Laurent.

The original AnkiVoice Core source code and project-specific documentation are licensed under the **PolyForm Noncommercial License 1.0.0**.

Commercial use is prohibited unless separately authorized by the copyright holder.

See the `LICENSE` file for the full license text.

This license applies only to the original AnkiVoice Core source code and project-specific documentation. It does not apply to third-party materials, dictionary contents, pronunciation audio files, service responses, media URLs, trademarks, user-provided files, or external libraries.

## Third-Party Rights

AnkiVoice Core does not claim ownership of any materials provided by NAVER Dictionary, NAVER Corporation, Anki, AnkiWeb, or any other third-party service.

NAVER, NAVER Dictionary, Anki, AnkiWeb, and related names, logos, trademarks, service names, contents, media files, service responses, and other materials remain the property of their respective owners.

Users are solely responsible for ensuring that their use of this software complies with applicable laws, third-party terms of service, API policies, robots.txt policies, copyright restrictions, and other usage restrictions.

## Usage Restrictions

Do not use AnkiVoice Core for:

* Commercial activities
* Unauthorized redistribution of third-party materials
* Bulk downloading
* Scraping, crawling, or database construction
* Circumventing access restrictions, authentication systems, or technical protection measures
* Copyright infringement
* Any use that violates applicable laws, third-party terms of service, API policies, or robots.txt policies

## About the `cryptography` Dependency

AnkiVoice Core includes a small optional Easter egg related to the developer's original creative work, *LAMINAE PROJECT*.

The `cryptography` package is used only to load an optional bundled content package for that Easter egg.

It is not part of the main Anki conversion or MP3 collection workflow. It does not collect personal data, decrypt user files, access credentials, bypass service restrictions, or perform hidden network operations.

In short: no conspiracy. Just a hidden Laminae Project joke.

## AI Assistance

This project was developed by Lutte Laurent with assistance from ChatGPT.

ChatGPT was used as a development assistance tool for code generation, refactoring, debugging, documentation drafting, and related technical support.

All AI-assisted outputs were reviewed, modified, and integrated by the human developer.

ChatGPT and OpenAI are not authors, maintainers, sponsors, official distributors, legal representatives, or third-party service providers of this project.

## Disclaimer

This software is provided **AS IS** and **AS AVAILABLE**, without warranty of any kind.

The developer does not guarantee that the software will work continuously, correctly, securely, or compatibly with any third-party service.

Third-party services may change their structure, access policies, response formats, API policies, or media delivery methods without notice.

Users use this software entirely at their own risk.
