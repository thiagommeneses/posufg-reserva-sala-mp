---
name: ia-clean-code
description: >-
  Clean Code naming conventions from Robert C. Martin's Chapter 2. Enforces
  intention-revealing names, meaningful distinctions, pronounceable and searchable
  names, no encodings, consistent lexicon, and proper use of domain terminology.
  Use when writing, modifying, reviewing, or refactoring code — any task that
  involves naming variables, functions, methods, classes, or modules.
metadata:
  author: André Teles
  version: '1.0.0'
  source: 'Clean Code by Robert C. Martin'
---

# Clean Code: Meaningful Names

Naming rules distilled from Chapter 2 of *Clean Code* by Robert C. Martin.
Apply these rules whenever you write or modify code. For detailed examples,
see [naming-rules.md](naming-rules.md).

## 1. Use Intention-Revealing Names

A name must tell **why it exists**, **what it does**, and **how it is used**.
If a name requires a comment to explain it, the name is wrong.

```java
// Bad
int d; // elapsed time in days

// Good
int elapsedTimeInDays;
int daysSinceCreation;
int fileAgeInDays;
```

## 2. Avoid Disinformation

Don't use names that convey false clues. Don't call a grouping `accountList`
unless it is actually a `List`. Prefer `accountGroup`, `accounts`, or
`bunchOfAccounts`.

```java
// Bad — not actually a List
Map<String, Account> accountList;

// Good
Map<String, Account> accountsByName;
```

## 3. Make Meaningful Distinctions

Never differentiate names by misspelling, number series (`a1`, `a2`), or
noise words (`Info`, `Data`). If names must differ, they must differ in meaning.

```java
// Bad
void copyChars(char[] a1, char[] a2) { ... }

// Good
void copyChars(char[] source, char[] destination) { ... }
```

## 4. Use Pronounceable Names

Names should be easy to say aloud. Programming is a social activity —
you need to discuss code with teammates.

```java
// Bad
Date genymdhms; // generation year, month, day, hour, minute, second

// Good
Date generationTimestamp;
```

## 5. Use Searchable Names

Single-letter names and numeric constants are hard to find. The length of a
name should correspond to the size of its scope.

```java
// Bad
for (int j = 0; j < 34; j++) {
    s += (t[j] * 4) / 5;
}

// Good
for (int j = 0; j < NUMBER_OF_TASKS; j++) {
    int realTaskDays = taskEstimate[j] * realDaysPerIdealDay;
    int realTaskWeeks = realTaskDays / WORK_DAYS_PER_WEEK;
    sum += realTaskWeeks;
}
```

## 6. Avoid Encodings

No Hungarian Notation. No member prefixes (`m_`). Don't prefix interfaces
with `I` — if you must encode, encode the *implementation* (`ShapeFactoryImpl`),
not the interface (`ShapeFactory`).

```java
// Bad
private String m_dsc;
IShapeFactory factory;

// Good
private String description;
ShapeFactory factory;
```

## 7. Avoid Mental Mapping

Readers should not have to mentally translate your names into concepts they
already know. Clarity is king — smart is not the same as professional.

```java
// Bad — reader must remember that r = lowercase url without host
String r = url.replace(host, "").toLowerCase();

// Good
String urlWithoutHost = url.replace(host, "").toLowerCase();
```

## 8. Class Names

Classes and objects should have **noun or noun-phrase** names: `Customer`,
`WikiPage`, `Account`, `AddressParser`. Avoid `Manager`, `Processor`, `Data`,
or `Info` in class names. A class name should never be a verb.

## 9. Method Names

Methods should have **verb or verb-phrase** names: `postPayment`, `deletePage`,
`save`. Accessors, mutators, and predicates use `get`, `set`, `is` prefixes.
Prefer static factory methods over overloaded constructors.

```java
// Good — factory method reveals intent
Complex fulcrumPoint = Complex.fromRealNumber(23.0);

// Worse — constructor hides intent
Complex fulcrumPoint = new Complex(23.0);
```

## 10. Don't Be Cute

Choose clarity over entertainment. Don't use slang or inside jokes.

```java
// Bad
void holyHandGrenade() { ... }
void whack() { ... }
void eatMyShorts() { ... }

// Good
void deleteItems() { ... }
void kill() { ... }
void abort() { ... }
```

## 11. Pick One Word per Concept

Choose one abstract word per concept and stick with it. Don't use `fetch`,
`retrieve`, and `get` as equivalent methods in different classes. A consistent
lexicon lets developers find the right method without memorizing which class
uses which synonym.

## 12. Don't Pun

Don't reuse a word for two different purposes. If existing `add` methods
concatenate two values, don't name a method that inserts into a collection
`add` — call it `insert` or `append`.

## 13. Use Solution Domain Names

You're writing code for programmers. Use CS terms: `AccountVisitor` (Visitor
pattern), `JobQueue`, `LinkedHashMap`. Don't avoid technical names out of
fear — they provide precise meaning.

## 14. Use Problem Domain Names

When no technical term fits, use the name from the problem domain. At least a
domain expert can explain what it means. Separating solution-domain from
problem-domain concepts is part of good design.

## 15. Add Meaningful Context

Most names are not meaningful alone. Place them in well-named classes,
functions, or namespaces. As a last resort, add a prefix.

```java
// Bad — ambiguous without context
String state;

// Good — context from class
class Address {
    String street;
    String city;
    String state;
    String zipCode;
}
```

## 16. Don't Add Gratuitous Context

Short names are better when clear. Don't prefix every class with the
application name. `Address` is fine for a class — `GSDAccountAddress` adds
17 characters of noise. `accountAddress` and `customerAddress` are fine for
instances.

## Quick Reference

| Rule | One-line summary |
|------|-----------------|
| Intention-Revealing | Name tells why, what, and how |
| No Disinformation | No false clues about type or purpose |
| Meaningful Distinctions | Different names = different meanings |
| Pronounceable | You can say it in conversation |
| Searchable | Grep-friendly; length matches scope |
| No Encodings | No type/scope prefixes |
| No Mental Mapping | No secret decoder ring needed |
| Noun Classes | Classes = nouns, never verbs |
| Verb Methods | Methods = verbs or verb phrases |
| No Cuteness | Clarity over cleverness |
| One Word per Concept | Consistent lexicon across codebase |
| No Puns | Same word = same semantic purpose |
| Solution Domain Names | Use CS terms when they fit |
| Problem Domain Names | Fall back to domain terms |
| Meaningful Context | Classes/namespaces provide context |
| No Gratuitous Context | Don't over-prefix |

For expanded examples and a self-assessment checklist, see
[naming-rules.md](naming-rules.md).
