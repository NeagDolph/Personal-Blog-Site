---
title: "Building a Crossword Generator with Constraint Satisfaction Programming"
date: 2025-06-25T10:00:00Z
description: "A deep dive into implementing Constraint Satisfaction Programming (CSP) for automatic crossword puzzle generation, breaking down complex AI concepts into understandable steps."
tags: ["ai", "csp", "constraint satisfaction", "algorithms", "python", "artificial intelligence", "optimization"]
categories: ["Artificial Intelligence"]
author: "Neil Agrawal"
showToc: true
showHero: true
---

# Building a Crossword Generator with Constraint Satisfaction Programming

Have you ever wondered how computers can automatically generate crossword puzzles? It turns out this seemingly simple task is actually a fascinating artificial intelligence problem that combines logic, optimization, and creative problem-solving. In this post, I'll walk you through how I implemented a crossword generator using **Constraint Satisfaction Programming (CSP)** as part of my CS4100 project, breaking down complex concepts into digestible pieces.

## What is Constraint Satisfaction Programming?

Before diving into crosswords, let's understand what CSP actually means. Imagine you're trying to schedule classes at a university:

- **Variables**: Each class that needs to be scheduled
- **Domains**: Available time slots for each class  
- **Constraints**: Rules like "Professors can't teach two classes at the same time" or "Classes for the same discipline cannot overlap"

CSP is a framework for solving problems where you need to assign values to variables while satisfying a set of constraints. 

For crosswords, this translates to:
- **Variables**: Empty slots where words can be placed
- **Domains**: Dictionary words that could fit in each slot
- **Constraints**: Words must intersect correctly and share the same letter at crossing points

## Why Crosswords Are Perfect for CSP

Crossword construction is actually much harder than it looks. A constructor needs to:

1. **Fill the grid efficiently** - maximize the percentage of filled squares
2. **Create valid intersections** - crossing words must share the correct letter
3. **Ensure connectivity** - all words must be linked through intersections

These requirements create a set of complex constraints that make crosswords a great problem for CSP algorithms.

## Step 1: Problem Formulation

### Defining Our Variables

The first step in any CSP implementation is identifying what we're trying to solve for. In our case, variables are **slots** - contiguous sequences of empty cells where words can be placed.

```python
class Slot:
    def __init__(self, start_row, start_col, direction, length, constraints={}):
        self.start_row = start_row
        self.start_col = start_col  
        self.length = length
        self.direction = direction  # 'across' or 'down'
        self.constraints = constraints
```

To find slots, we systematically scan the grid:

```python
def _find_slots_in_direction(grid: CrosswordGrid, direction: Direction, min_length: int = 3) -> List[Slot]:
    slots: List[Slot] = []
    is_horizontal = direction == Direction.ACROSS
    
    for outer in range(grid.size):
        # Find all black square positions in this row/column
        black_positions = []
        for inner in range(grid.size):
            row, col = (outer, inner) if is_horizontal else (inner, outer)
            if grid.is_blocked(row, col):
                black_positions.append(inner)
        
        # Create segments between black squares (including start and end)
        segment_starts = [0] + [pos + 1 for pos in black_positions]
        segment_ends = black_positions + [grid.size]
        
        # Process each segment to create slots
        for start, end in zip(segment_starts, segment_ends):
            segment_length = end - start
            
            # Skip segments that are too short
            if segment_length < min_length:
                continue
            
            # Build constraints for this segment
            constraints = {}
            for pos in range(start, end):
                row, col = (outer, pos) if is_horizontal else (pos, outer)
                letter = grid.get_letter(row, col)
                if letter:
                    constraints[pos - start] = str(letter)
            
            # Create slot for this segment
            start_row, start_col = (outer, start) if is_horizontal else (start, outer)
            slot = Slot(start_row, start_col, direction, segment_length, constraints)
            slots.append(slot)

    return slots
```



## Step 2: Efficient Constraint Propagation

One of the biggest challenges in CSP is making constraint checking fast. With thousands of words in our dictionary, naively checking every constraint for every word becomes computationally expensive.

### The Problem

Without optimization, finding compatible words for a slot with multiple constraints requires checking each word against each constraint individually. For a slot intersecting with 3 other words, this means:

```
For each word in dictionary (837 words):
    For each constraint (3 constraints):
        Check if word satisfies constraint
```

This gives us **O(|D| × c)** complexity, where |D| is dictionary size and c is the number of constraints.

### The Solution: Pre-computed Indexes

Instead, we pre-compute a position-letter index that maps (position, letter) pairs to sets of compatible words:

```python
def _build_indexes(self):
    all_words = self.word_data_manager.get_all_words()
    
    for word in all_words:
        word_len = len(word)
        self.length_index[word_len].append(word)
        
        # Build position-letter index
        word_upper = word.upper()
        for pos, letter in enumerate(word_upper):
            self.position_letter_index[(pos, letter)].add(word)

```

We can then use the pre-computed index to easily find compatible words for all constraints by iteratively **intersecting sets** of compatible words for each constraint.

```python
 def find_compatible_words(self, slot: Slot, max_results: int = 100) -> List[str]:
        min_word_length = 3
        
        # Sort constraints by position (lowest to highest)
        sorted_constraints = sorted(slot.constraints.items(), key=lambda x: x[0])
        
        compatible_words = None
        min_required_length = max(pos + 1 for pos, _ in sorted_constraints)  # Minimum length to satisfy all constraints
        
        for pos, required_letter in sorted_constraints:
            # Get all words that have the required letter at this position
            words_with_letter = self.position_letter_index.get((pos, str(required_letter).upper()), set())
            
            # Filter by length requirements:
            # - Word must be at least long enough to reach this constraint position
            # - Word must not be longer than the slot
            valid_length_words = {w for w in words_with_letter 
                                if min_word_length <= len(w) <= slot.length and len(w) > pos}
            
            # Intersect compatible word for current constraint with compatible words for previous constraints
            compatible_words = valid_length_words if compatible_words is None else compatible_words.intersection(valid_length_words)
        
        return compatible_words[:max_results]
```

This reduces our complexity to **O(c × k)**, where k is the average size of constraint-satisfying word sets - a massive improvement!

## Step 3: Heuristics for Slot Selection

Not all slots are created equal. Some are easier to fill, some create more opportunities for intersections, and some are more critical to the puzzle's structure. We need smart heuristics to decide which slot to fill next.

### Multi-Objective Heuristic Function

Our heuristic combines multiple factors:

```python
def calculate_slot_score(slot):
    # Feasibility (more compatible words = easier to fill)
    domain_size = len(find_compatible_words(slot)) * 20
    
    # Constraint pressure (more constraints = higher priority)
    constraint_score = len(slot.constraints) * 15

    # Length preference (prefer longer slots)
    length_score = slot.length * 5
    
    return domain_size + constraint_score + length_score
```

### The Selection Strategy

Rather than always picking the highest-scoring slot (which can lead to predictable, suboptimal choices), we use **controlled randomness**:

```python
# Score all unassigned slots and then sort them in descending order
scored_slots = [(slot, calculate_slot_score(slot)) for slot in unassigned_slots]
scored_slots.sort(key=lambda x: x[1], reverse=True)

# Pick randomly from the top N candidates
top_n = min(5, len(scored_slots))
return random.choice(scored_slots[:top_n])[0]
```

This approach balances exploitation (using our heuristic knowledge) with exploration (maintaining some randomness to avoid local optima).

## Step 4: Search Strategy with Intelligent Backtracking

### Forward Search with Constraint Propagation

Our main search loop follows a forward-chaining approach:

```python
for iteration in range(max_iterations):
    current_fill = calculate_fill_percentage(creator)
    
    # Find slots that intersect with existing words (ensures connectivity)
    empty_slots = find_intersecting_slots(creator.grid, creator.word_placements)
    
    # Score and select from top N slots
    scored_slots = [(slot, score_slot(slot, creator)) for slot in empty_slots]
    scored_slots.sort(key=lambda x: x[1], reverse=True)
    
    top_slots = scored_slots[:3]  # Top 3 candidates
    selected_slot = random.choice(top_slots)[0]
    
    # Get available words (excluding already used)
    compatible_words = find_compatible_words(selected_slot)
    available_words = [w for w in compatible_words if w not in used_words]
    
    if not available_words:
        consecutive_failures += 1
        if consecutive_failures >= 5:  # Backtrack threshold
            backtrack_success = backtrack(creator, used_words)
            consecutive_failures = 0 if backtrack_success else consecutive_failures
        continue
    
    # Select and place word
    selected_word = random.choice(available_words[:3])  # Top 3 words
    
    if place_word(creator, selected_word, selected_slot):
        used_words.add(selected_word)
```

### Smart Backtracking Strategy

When we hit a dead end (no compatible words for a slot), we need to backtrack intelligently:

```python
def _backtrack(self, creator: CrosswordCreator, used_words: Set[str]) -> bool:
    # Exponential distribution ensures smaller backtrack values are much more common than larger values
    num_to_remove = exponential_random_num(len(creator.word_placements)) 
    
    # Get the last N word placements (most recently added)
    words_to_remove = creator.word_placements[-num_to_remove:]
    removed_count = 0
    
    # Remove words from most recent to oldest
    for word_placement in reversed(words_to_remove):
        removed_word = word_placement.word.upper()
        success = creator.remove_word(word_placement)
        if success:
            used_words.discard(removed_word)
            removed_count += 1
    
    return removed_count > 0
```

This exponential falloff means we're more likely to remove just one word (local backtrack) than many words (global restart), but we maintain the ability to escape local optima when necessary.

## Step 5: Results and Analysis

### Performance Metrics

Our CSP implementation achieved impressive results across different difficulty levels:

| Difficulty | Grid Size | Target Fill | Actual Fill | Words Placed | Generation Time |
|------------|-----------|-------------|-------------|--------------|-----------------|
| Easy       | 8×8       | 60%         | 66.7%       | 7            | 80ms           |
| Medium     | 11×11     | 70%         | 71.7%       | 13           | 230ms          |
| Hard       | 14×14     | 80%         | 80.2%       | 23           | 520ms          |

### Why CSP Works So Well for Crosswords

1. **Systematic Approach**: CSP naturally models the constraint-heavy nature of crossword construction
2. **Efficient Pruning**: Constraint propagation eliminates invalid options early
3. **Scalable**: Performance scales well with grid size due to efficient data structures

## Key Takeaways for Implementing CSP

### 1. Model Carefully
Spend time identifying your variables, domains, and constraints clearly. A good model is half the battle.

### 2. Optimize Early
Constraint checking can quickly become a bottleneck. Pre-computed indexes and efficient data structures make it all possible.

### 3. Use Smart Heuristics
Your heuristic function directly impacts solution quality. Combine multiple factors and use controlled randomness.

### 4. Plan for Backtracking
Dead ends are inevitable in complex CSPs. Design your backtracking strategy to balance exploration vs exploitation.

## Beyond Crosswords: Other CSP Applications

The techniques we used for crossword generation apply to many other domains:

- **Scheduling**: Class scheduling, employee shifts, resource allocation
- **Configuration**: Product configuration, network routing, chip design  
- **Planning**: Route planning, task assignment, resource management
- **Games**: Sudoku solving, map coloring, n-queens problem

The key insight is recognizing when a problem has the structure of variables, domains, and constraints that CSP can exploit.

## Future Improvements

Our current implementation could be enhanced in several ways:

1. **Better Word Selection**: Incorporate clue difficulty and theme consistency
2. **Advanced Constraints**: Prevent accidental word formation in parallel slots
3. **Interactive Generation**: Allow human constructors to guide the process

## Conclusion

Implementing CSP for crossword generation taught me that artificial intelligence isn't just about complex neural networks and machine learning. Sometimes, the most elegant solutions come from carefully modeling a problem's structure and applying systematic search techniques.

The combination of efficient constraint propagation, heuristics, and backtracking allowed our CSP solver to generate high-quality crosswords in milliseconds. More importantly, the systematic approach provided predictable, reliable results - exactly what you want when building production systems.

---

*Want to dive deeper into the technical details? Check out the [full research paper](/papers/CS4100_Project_Report.pdf) and [implementation](https://github.com/NeagDolph/CS4100-crossword-generator) on GitHub.*