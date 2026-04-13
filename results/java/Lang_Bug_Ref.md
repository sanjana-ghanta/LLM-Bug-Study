# Lang Bug Reference

All 59 active bugs from the Lang project in Defects4J.
Files appearing in multiple bugs are **bolded** — these are high-risk for LLM pattern-matching.

## File frequency

| File | Bug count |
|------|-----------|
| **NumberUtils.java** | 9 |
| **StringUtils.java** | 6 |
| **FastDateFormat.java** | 4 |
| **StrBuilder.java** | 4 |
| **LocaleUtils.java** | 3 |
| **FastDateParser.java** | 2 |
| **RandomStringUtils.java** | 2 |
| **CharSequenceTranslator.java** | 2 |
| **NumericEntityUnescaper.java** | 2 |
| **DateUtils.java** | 2 |
| **Fraction.java** | 2 |
| **ExtendedMessageFormat.java** | 2 |
| **ClassUtils.java** | 2 |
| **ArrayUtils.java** | 2 |
| **StringEscapeUtils.java** | 2 |

## Bug map

| Bug ID | Jira | File | Line | Mutation type | Exception / root cause |
|--------|------|------|------|---------------|------------------------|
| Lang_1  | [LANG-747](https://issues.apache.org/jira/browse/LANG-747) | **NumberUtils.java** | 466 | off_by_one | `NumberFormatException: For input string: "80000000"` |
| Lang_3  | [LANG-693](https://issues.apache.org/jira/browse/LANG-693) | **NumberUtils.java** | 592 | off_by_one | `AssertionFailedError` |
| Lang_4  | [LANG-882](https://issues.apache.org/jira/browse/LANG-882) | LookupTranslator.java | 31 | operator_swap | `AssertionFailedError: Incorrect codepoint` |
| Lang_5  | [LANG-865](https://issues.apache.org/jira/browse/LANG-865) | **LocaleUtils.java** | 96 | off_by_one | `IllegalArgumentException: Invalid locale format` |
| Lang_6  | [LANG-857](https://issues.apache.org/jira/browse/LANG-857) | **CharSequenceTranslator.java** | 95 | off_by_one | `StringIndexOutOfBoundsException` |
| Lang_7  | [LANG-822](https://issues.apache.org/jira/browse/LANG-822) | **NumberUtils.java** | 720 | off_by_one | `AssertionFailedError: Expected NumberFormatException` |
| Lang_8  | [LANG-818](https://issues.apache.org/jira/browse/LANG-818) | FastDatePrinter.java | 1098 | off_by_one | `AssertionFailedError: expected:<2:43PM [IC]T>` |
| Lang_9  | [LANG-832](https://issues.apache.org/jira/browse/LANG-832) | **FastDateParser.java** | 143 | off_by_one | `AssertionFailedError: Expected FDF failure` |
| Lang_10 | [LANG-831](https://issues.apache.org/jira/browse/LANG-831) | **FastDateParser.java** | 304 | off_by_one | `AssertionFailedError: Expected FDF failure` |
| Lang_11 | [LANG-807](https://issues.apache.org/jira/browse/LANG-807) | **RandomStringUtils.java** | 243 | operator_swap | `AssertionFailedError: bound must be positive` |
| Lang_12 | [LANG-805](https://issues.apache.org/jira/browse/LANG-805) | **RandomStringUtils.java** | 229 | operator_swap | `ArrayIndexOutOfBoundsException: 1859709389` |
| Lang_13 | [LANG-788](https://issues.apache.org/jira/browse/LANG-788) | SerializationUtils.java | 238 | none | `SerializationException: ClassNotFoundException` |
| Lang_14 | [LANG-786](https://issues.apache.org/jira/browse/LANG-786) | **StringUtils.java** | 787 | off_by_one | `AssertionFailedError` |
| Lang_15 | [LANG-775](https://issues.apache.org/jira/browse/LANG-775) | TypeUtils.java | 675 | off_by_one | `AssertionFailedError: type class mismatch` |
| Lang_16 | [LANG-746](https://issues.apache.org/jira/browse/LANG-746) | **NumberUtils.java** | 458 | off_by_one | `NumberFormatException: 0Xfade is not valid` |
| Lang_17 | [LANG-720](https://issues.apache.org/jira/browse/LANG-720) | **CharSequenceTranslator.java** | 83 | off_by_one | `ComparisonFailure: expected:<𠮷[A]>` |
| Lang_19 | [LANG-710](https://issues.apache.org/jira/browse/LANG-710) | **NumericEntityUnescaper.java** | 40 | operator_swap | `StringIndexOutOfBoundsException` |
| Lang_20 | [LANG-703](https://issues.apache.org/jira/browse/LANG-703) | **StringUtils.java** | 3298 | off_by_one | `NullPointerException` |
| Lang_21 | [LANG-677](https://issues.apache.org/jira/browse/LANG-677) | **DateUtils.java** | ? | off_by_one | `AssertionFailedError: LANG-677` |
| Lang_22 | [LANG-662](https://issues.apache.org/jira/browse/LANG-662) | Fraction.java | ? | operator_swap | `AssertionFailedError: expected:<-1073741824>` |
| Lang_23 | [LANG-636](https://issues.apache.org/jira/browse/LANG-636) | **ExtendedMessageFormat.java** | ? | off_by_one | `AssertionFailedError: registry, hashcode()` |
| Lang_24 | [LANG-664](https://issues.apache.org/jira/browse/LANG-664) | **NumberUtils.java** | ? | off_by_one | `AssertionFailedError: isNumber(String) LANG-664` |
| Lang_26 | [LANG-645](https://issues.apache.org/jira/browse/LANG-645) | **FastDateFormat.java** | ? | off_by_one | `ComparisonFailure: expected:<fredag, week [5]>` |
| Lang_27 | [LANG-638](https://issues.apache.org/jira/browse/LANG-638) | **NumberUtils.java** | ? | off_by_one | `StringIndexOutOfBoundsException` |
| Lang_28 | [LANG-617](https://issues.apache.org/jira/browse/LANG-617) | **NumericEntityUnescaper.java** | ? | operator_swap | `ComparisonFailure: Failed to unescape numeric` |
| Lang_29 | [LANG-624](https://issues.apache.org/jira/browse/LANG-624) | SystemUtils.java | ? | off_by_one | `AssertionFailedError: expected:<0> but was:<1>` |
| Lang_30 | [LANG-607](https://issues.apache.org/jira/browse/LANG-607) | **StringUtils.java** | ? | off_by_one | `AssertionFailedError: expected:<true>` |
| Lang_31 | [LANG-607](https://issues.apache.org/jira/browse/LANG-607) | **StringUtils.java** | ? | off_by_one | `AssertionFailedError: expected:<false>` |
| Lang_32 | [LANG-586](https://issues.apache.org/jira/browse/LANG-586) | HashCodeBuilder.java | ? | off_by_one | `AssertionFailedError: Expected: <null>` |
| Lang_33 | [LANG-587](https://issues.apache.org/jira/browse/LANG-587) | ClassUtils.java | ? | off_by_one | `NullPointerException` |
| Lang_34 | [LANG-586](https://issues.apache.org/jira/browse/LANG-586) | ToStringStyle.java | ? | off_by_one | `AssertionFailedError: Expected: <null>` |
| Lang_35 | [LANG-571](https://issues.apache.org/jira/browse/LANG-571) | **ArrayUtils.java** | ? | off_by_one | `ClassCastException: [Ljava.lang.Object cannot be cast` |
| Lang_36 | [LANG-521](https://issues.apache.org/jira/browse/LANG-521) | **NumberUtils.java** | ? | off_by_one | `AssertionFailedError: isNumber(String) LANG-521` |
| Lang_37 | [LANG-567](https://issues.apache.org/jira/browse/LANG-567) | **ArrayUtils.java** | ? | off_by_one | `ArrayStoreException` |
| Lang_38 | [LANG-538](https://issues.apache.org/jira/browse/LANG-538) | **FastDateFormat.java** | ? | off_by_one | `ComparisonFailure: dateTime expected` |
| Lang_39 | [LANG-552](https://issues.apache.org/jira/browse/LANG-552) | **StringUtils.java** | ? | off_by_one | `NullPointerException` |
| Lang_40 | [LANG-432](https://issues.apache.org/jira/browse/LANG-432) | **StringUtils.java** | ? | off_by_one | `AssertionFailedError: en: 0 ß SS` |
| Lang_41 | [LANG-535](https://issues.apache.org/jira/browse/LANG-535) | **ClassUtils.java** | ? | off_by_one | `ComparisonFailure: expected:<[]java.lang>` |
| Lang_42 | [LANG-480](https://issues.apache.org/jira/browse/LANG-480) | Entities.java | ? | off_by_one | `ComparisonFailure: High unicode was not escaped` |
| Lang_43 | [LANG-477](https://issues.apache.org/jira/browse/LANG-477) | **ExtendedMessageFormat.java** | ? | off_by_one | `OutOfMemoryError: Java heap space` |
| Lang_44 | [LANG-457](https://issues.apache.org/jira/browse/LANG-457) | **NumberUtils.java** | ? | off_by_one | `StringIndexOutOfBoundsException` |
| Lang_45 | [LANG-419](https://issues.apache.org/jira/browse/LANG-419) | WordUtils.java | ? | off_by_one | `StringIndexOutOfBoundsException` |
| Lang_46 | [LANG-421](https://issues.apache.org/jira/browse/LANG-421) | **StringEscapeUtils.java** | ? | off_by_one | `ComparisonFailure: expected string mismatch` |
| Lang_47 | [LANG-412](https://issues.apache.org/jira/browse/LANG-412) | **StrBuilder.java** | ? | off_by_one | `NullPointerException` |
| Lang_49 | [LANG-380](https://issues.apache.org/jira/browse/LANG-380) | Fraction.java | ? | operator_swap | `AssertionFailedError: expected:<1> but was:<0>` |
| Lang_50 | [LANG-368](https://issues.apache.org/jira/browse/LANG-368) | **FastDateFormat.java** | ? | off_by_one | `AssertionFailedError: expected same:<de_DE>` |
| Lang_51 | [LANG-365](https://issues.apache.org/jira/browse/LANG-365) | BooleanUtils.java | ? | off_by_one | `StringIndexOutOfBoundsException` |
| Lang_52 | [LANG-363](https://issues.apache.org/jira/browse/LANG-363) | **StringEscapeUtils.java** | ? | off_by_one | `ComparisonFailure: script escape mismatch` |
| Lang_53 | [LANG-346](https://issues.apache.org/jira/browse/LANG-346) | **DateUtils.java** | ? | off_by_one | `AssertionFailedError: Minute Round Up Failed` |
| Lang_54 | [LANG-328](https://issues.apache.org/jira/browse/LANG-328) | **LocaleUtils.java** | ? | off_by_one | `IllegalArgumentException: Invalid locale format` |
| Lang_55 | [LANG-315](https://issues.apache.org/jira/browse/LANG-315) | StopWatch.java | ? | operator_swap | `AssertionFailedError` |
| Lang_56 | [LANG-303](https://issues.apache.org/jira/browse/LANG-303) | **FastDateFormat.java** | ? | off_by_one | `SerializationException: java.io.NotSerializable` |
| Lang_57 | [LANG-304](https://issues.apache.org/jira/browse/LANG-304) | **LocaleUtils.java** | ? | off_by_one | `NullPointerException` |
| Lang_58 | [LANG-300](https://issues.apache.org/jira/browse/LANG-300) | **NumberUtils.java** | ? | off_by_one | `NumberFormatException: 1l is not a valid number` |
| Lang_59 | [LANG-299](https://issues.apache.org/jira/browse/LANG-299) | **StrBuilder.java** | ? | off_by_one | `ArrayIndexOutOfBoundsException` |
| Lang_60 | [LANG-295](https://issues.apache.org/jira/browse/LANG-295) | **StrBuilder.java** | ? | off_by_one | `AssertionFailedError: The contains(char) method` |
| Lang_61 | [LANG-294](https://issues.apache.org/jira/browse/LANG-294) | **StrBuilder.java** | ? | off_by_one | `ArrayIndexOutOfBoundsException` |

> **Note:** `?` in the Line column means `extract_bug_line.py` has not yet been run for that bug. Lines will be filled in after extraction.

> **Bold files** appear in 2+ bugs and are high-risk for LLM pattern-matching false positives.
