# Naming Rules — Detailed Reference

Expanded rules with idiomatic Java examples. Source: *Clean Code*, Chapter 2.

---

## 1. Use Intention-Revealing Names

The name of a variable, function, or class should answer: **why does it
exist?** **What does it do?** **How is it used?** If you need a comment, the
name does not reveal its intent.

**Bad:**

```java
public List<int[]> getThem() {
    List<int[]> list1 = new ArrayList<>();
    for (int[] x : theList)
        if (x[0] == 4)
            list1.add(x);
    return list1;
}
```

What is `theList`? What does index `0` mean? What is the value `4`? The code
is simple, but the context is completely implicit.

**Good:**

```java
public List<Cell> getFlaggedCells() {
    List<Cell> flaggedCells = new ArrayList<>();
    for (Cell cell : gameBoard)
        if (cell.isFlagged())
            flaggedCells.add(cell);
    return flaggedCells;
}
```

Same logic, but now every name reveals its intent.

---

## 2. Avoid Disinformation

Don't use names whose established meaning differs from your intended meaning.
`hp`, `aix`, `sco` look like Unix platform names. Don't call something a
`List` unless it really is a `java.util.List`.

**Bad:**

```java
Set<Account> accountList; // misleading — it's a Set, not a List
```

**Good:**

```java
Set<Account> accounts;
Map<String, Account> accountsByName;
```

Also avoid names that look almost identical:

```java
// Bad — spot the difference at a glance?
XYZControllerForEfficientHandlingOfStrings
XYZControllerForEfficientStorageOfStrings
```

---

## 3. Make Meaningful Distinctions

If the compiler requires different names, don't satisfy it with number series
or noise words.

**Bad — number series:**

```java
public static void copyChars(char[] a1, char[] a2) {
    for (int i = 0; i < a1.length; i++) {
        a2[i] = a1[i];
    }
}
```

**Good:**

```java
public static void copyChars(char[] source, char[] destination) {
    for (int i = 0; i < source.length; i++) {
        destination[i] = source[i];
    }
}
```

**Bad — noise words:**

```java
class Product { }
class ProductInfo { }   // what's the difference?
class ProductData { }   // what's the difference?
```

`Info` and `Data` are noise — like `a`, `an`, and `the` as prefixes. If names
must differ, they must mean different things.

---

## 4. Use Pronounceable Names

If you can't pronounce a name, you can't discuss it without sounding absurd.

**Bad:**

```java
class DtaRcrd102 {
    private Date genymdhms;
    private Date modymdhms;
    private final String pszqint = "102";
}
```

**Good:**

```java
class Customer {
    private Date generationTimestamp;
    private Date modificationTimestamp;
    private final String recordId = "102";
}
```

Now you can say: "Hey, look at this customer's generation timestamp — it's
set to tomorrow!"

---

## 5. Use Searchable Names

Single-letter names and literal constants are impossible to grep for. The
length of a name should be proportional to the size of its scope.

**Bad:**

```java
for (int j = 0; j < 34; j++) {
    s += (t[j] * 4) / 5;
}
```

**Good:**

```java
int realDaysPerIdealDay = 4;
const int WORK_DAYS_PER_WEEK = 5;
int sum = 0;

for (int j = 0; j < NUMBER_OF_TASKS; j++) {
    int realTaskDays = taskEstimate[j] * realDaysPerIdealDay;
    int realTaskWeeks = realTaskDays / WORK_DAYS_PER_WEEK;
    sum += realTaskWeeks;
}
```

`WORK_DAYS_PER_WEEK` is much easier to find than the bare number `5`.

---

## 6. Avoid Encodings

### Hungarian Notation

Modern IDEs and compilers handle type information — encoding it in names
adds clutter and maintenance burden.

**Bad:**

```java
String strName;
int iAge;
boolean bIsActive;
```

**Good:**

```java
String name;
int age;
boolean active;
```

### Member Prefixes

Don't use `m_` or similar prefixes. Keep classes and methods small enough
that you can see member variables at a glance.

**Bad:**

```java
public class Part {
    private String m_dsc; // textual description
    void setName(String name) {
        m_dsc = name;
    }
}
```

**Good:**

```java
public class Part {
    private String description;
    void setDescription(String description) {
        this.description = description;
    }
}
```

### Interface and Implementation

Don't prefix interfaces with `I`. If you must encode one side, encode the
implementation.

**Bad:** `IShapeFactory` + `ShapeFactory`

**Good:** `ShapeFactory` (interface) + `ShapeFactoryImpl` or `CShapeFactory`

---

## 7. Avoid Mental Mapping

Readers should not have to mentally translate your names. A single-letter
loop counter `i` is tolerable by convention, but `r` as a lowercase URL
without host and context is not.

> A difference between a smart programmer and a professional: the
> professional understands that **clarity is king**.

**Bad:**

```java
String r = uri.replace(host, "");
// reader must remember: r = processed URL path
```

**Good:**

```java
String urlPath = uri.replace(host, "");
```

---

## 8. Class Names

Classes and objects should be named with **nouns or noun phrases**.

**Good:** `Customer`, `WikiPage`, `Account`, `AddressParser`

**Bad:** `Manager`, `Processor`, `Data`, `Info`

A class name should **never be a verb**.

---

## 9. Method Names

Methods should be named with **verbs or verb phrases**.

**Good:** `postPayment()`, `deletePage()`, `save()`

Accessors, mutators, and predicates follow the JavaBean convention:

```java
String name = employee.getName();
customer.setName("Mike");
if (paycheck.isPosted()) { ... }
```

When constructors are overloaded, use **static factory methods** with names
that describe the arguments:

```java
// Good — reveals intent
Complex fulcrumPoint = Complex.fromRealNumber(23.0);

// Worse — what does 23.0 mean?
Complex fulcrumPoint = new Complex(23.0);
```

---

## 10. Don't Be Cute

If names are too clever, only people who share the author's sense of humor
will remember them — and only while the joke is funny.

| Cute | Clean |
|------|-------|
| `holyHandGrenade()` | `deleteItems()` |
| `whack()` | `kill()` |
| `eatMyShorts()` | `abort()` |

Say what you mean. Mean what you say.

---

## 11. Pick One Word per Concept

Pick one word for each abstract concept and stick with it. Having `fetch`,
`retrieve`, and `get` as equivalent methods of different classes is confusing.

Similarly, don't have a `controller`, a `manager`, and a `driver` in the same
codebase for the same concept. What is the essential difference between a
`DeviceManager` and a `ProtocolController`?

A consistent lexicon is a great advantage for developers navigating your code.

---

## 12. Don't Pun

Using the same word for two different ideas is a pun. If you have many
classes with an `add` method that creates a new value by combining two
existing values, don't also call a method that inserts a single element into
a collection `add`. That would be a pun. Use `insert` or `append` instead.

---

## 13. Use Solution Domain Names

Your readers are programmers. Use computer science terms freely:
`AccountVisitor` (Visitor pattern), `JobQueue`, `LinkedHashMap`.

Don't avoid a well-known technical name because the domain expert wouldn't
know it — you're writing code for developers.

---

## 14. Use Problem Domain Names

When there is no programmer-oriented term, use the name from the problem
domain. At least a domain expert can explain what it means. Separating
solution-domain concepts from problem-domain concepts is part of the
designer's job.

---

## 15. Add Meaningful Context

Few names are meaningful in isolation. Place them in well-named classes,
functions, or namespaces. As a last resort, prefix them.

**Bad — variables with unclear context:**

```java
private void printGuessStatistics(char candidate, int count) {
    String number;
    String verb;
    String pluralModifier;
    if (count == 0) {
        number = "no";
        verb = "are";
        pluralModifier = "s";
    } else if (count == 1) {
        number = "1";
        verb = "is";
        pluralModifier = "";
    } else {
        number = Integer.toString(count);
        verb = "are";
        pluralModifier = "s";
    }
    String guessMessage = String.format(
        "There %s %s %s%s", verb, number, candidate, pluralModifier
    );
    print(guessMessage);
}
```

**Good — variables have context from the class:**

```java
public class GuessStatisticsMessage {
    private String number;
    private String verb;
    private String pluralModifier;

    public String make(char candidate, int count) {
        createPluralDependentMessageParts(count);
        return String.format(
            "There %s %s %s%s",
            verb, number, candidate, pluralModifier);
    }

    private void createPluralDependentMessageParts(int count) {
        if (count == 0) {
            thereAreNoLetters();
        } else if (count == 1) {
            thereIsOneLetter();
        } else {
            thereAreManyLetters(count);
        }
    }

    private void thereAreManyLetters(int count) {
        number = Integer.toString(count);
        verb = "are";
        pluralModifier = "s";
    }

    private void thereIsOneLetter() {
        number = "1";
        verb = "is";
        pluralModifier = "";
    }

    private void thereAreNoLetters() {
        number = "no";
        verb = "are";
        pluralModifier = "s";
    }
}
```

The three variables are now **definitively** part of `GuessStatisticsMessage`.

---

## 16. Don't Add Gratuitous Context

In an application called "Gas Station Deluxe" (GSD), don't prefix every class
with `GSD`. You'd fight the IDE's autocomplete.

Short names are generally better, provided they are clear.

- `accountAddress` and `customerAddress` are fine for instances of `Address`.
- `Address` is fine for a class.
- `PostalAddress`, `MAC`, and `URI` are fine when disambiguation is needed.
- `GSDAccountAddress` is 17 characters of noise.

---

## Self-Assessment Checklist

Before submitting code, review your names against this checklist:

- [ ] Can I understand each name without reading its implementation?
- [ ] Are there any single-letter variables outside tiny loop scopes?
- [ ] Do any names contain noise words (Info, Data, Manager, Processor)?
- [ ] Can I pronounce every name?
- [ ] Can I grep for every name and find it easily?
- [ ] Are there any encoded types, prefixes, or Hungarian Notation artifacts?
- [ ] Does each class name use a noun or noun phrase?
- [ ] Does each method name use a verb or verb phrase?
- [ ] Am I using one word per concept consistently?
- [ ] Am I reusing any word for two semantically different operations?
- [ ] Do variables have enough context from their enclosing class or function?
- [ ] Are there unnecessary application-level prefixes on class names?
