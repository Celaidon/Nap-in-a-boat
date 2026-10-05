"""
Rhyme and meter scorer for poetry evaluation using the pronouncing package.
Scores rhyme scheme (AABB, ABAB, adjacent) and meter consistency (syllable count variance).
"""

import re
import statistics

import pronouncing


def _clean_word(word: str) -> str:
    """Strip punctuation and normalize word."""
    cleaned = re.sub(r"[^\w\s]", "", word).strip().lower()
    return cleaned


def _get_syllable_count(line: str) -> int:
    """Estimate total syllable count for a line of text."""
    words = [_clean_word(w) for w in line.split() if _clean_word(w)]
    count = 0
    for w in words:
        phones = pronouncing.phones_for_word(w)
        if phones:
            count += pronouncing.syllable_count(phones[0])
        else:
            # Fallback vowel counting heuristic for unknown words
            vowels = re.findall(r"[aeiouyAEIOUY]+", w)
            count += max(1, len(vowels))
    return max(1, count)


def _words_rhyme(w1: str, w2: str) -> bool:
    """Check if two words rhyme using pronouncing library."""
    if not w1 or not w2:
        return False
    if w1 == w2:
        # Same word isn't usually considered a clean rhyme, but has sound match
        return True

    rhymes1 = set(pronouncing.rhymes(w1))
    if w2 in rhymes1:
        return True

    rhymes2 = set(pronouncing.rhymes(w2))
    if w1 in rhymes2:
        return True

    # Check phone suffix matching (rhyming part)
    p1 = pronouncing.phones_for_word(w1)
    p2 = pronouncing.phones_for_word(w2)
    if p1 and p2:
        rhyme_part1 = pronouncing.rhyming_part(p1[0])
        rhyme_part2 = pronouncing.rhyming_part(p2[0])
        if rhyme_part1 and rhyme_part2 and rhyme_part1 == rhyme_part2:
            return True

    return False


def rhyme_score(poem: str) -> float:
    """Calculate rhyme and meter score (0.0 to 1.0) for a given poem.

    Args:
        poem: Multi-line string poem text.

    Returns:
        float: Score between 0.0 and 1.0.
    """
    if not poem or not poem.strip():
        return 0.0

    lines = [line.strip() for line in poem.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return 0.0

    # Extract last word of each line
    end_words = []
    for line in lines:
        tokens = line.split()
        if tokens:
            end_words.append(_clean_word(tokens[-1]))

    n_lines = len(end_words)
    if n_lines < 2:
        return 0.0

    # 1. Adjacent pairs rhyme ratio (0-1, 1-2, 2-3...)
    adj_matches = sum(1 for i in range(n_lines - 1) if _words_rhyme(end_words[i], end_words[i + 1]))
    adj_ratio = adj_matches / (n_lines - 1)

    # 2. AABB / ABAB patterns for groups of 4 lines
    aabb_matches = 0
    abab_matches = 0
    total_quads = 0

    for i in range(0, n_lines - 3, 2):
        total_quads += 1
        # AABB: (0, 1) and (2, 3)
        if _words_rhyme(end_words[i], end_words[i + 1]) or _words_rhyme(end_words[i + 2], end_words[i + 3]):
            aabb_matches += 1
        # ABAB: (0, 2) and (1, 3)
        if _words_rhyme(end_words[i], end_words[i + 2]) or _words_rhyme(end_words[i + 1], end_words[i + 3]):
            abab_matches += 1

    pattern_ratio = max(aabb_matches, abab_matches) / max(1, total_quads) if total_quads > 0 else 0.0

    rhyme_component = max(adj_ratio, pattern_ratio)

    # 3. Meter consistency (variance in syllable count per line)
    syllable_counts = [_get_syllable_count(line) for line in lines]
    if len(syllable_counts) > 1:
        mean_s = statistics.mean(syllable_counts)
        stdev_s = statistics.stdev(syllable_counts)
        meter_component = max(0.0, min(1.0, 1.0 - (stdev_s / max(1.0, mean_s))))
    else:
        meter_component = 0.5

    # Composite score weighted 70% rhyme, 30% meter
    final_score = (0.7 * rhyme_component) + (0.3 * meter_component)
    return float(round(max(0.0, min(1.0, final_score)), 2))
