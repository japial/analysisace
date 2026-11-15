import { describe, expect, it } from "vitest";

import { formatBDT, formatCompactBDT, formatDate, formatNumber, formatPercent } from "./format";

describe("formatNumber", () => {
  it("groups in lakh and crore", () => {
    expect(formatNumber(1234567)).toBe("12,34,567");
    expect(formatNumber("123456789.5")).toBe("12,34,56,789.5");
  });

  it("uses Bangla digits when asked", () => {
    expect(formatNumber(1234567, { digits: "bn" })).toBe("১২,৩৪,৫৬৭");
  });

  it("rejects values that are not decimals", () => {
    expect(() => formatNumber("12abc")).toThrow(RangeError);
    expect(() => formatNumber(Number.NaN)).toThrow(RangeError);
  });
});

describe("formatBDT", () => {
  it("formats an API decimal string with two decimals", () => {
    expect(formatBDT("304.2000")).toBe("৳304.20");
    expect(formatBDT("1234567.5")).toBe("৳12,34,567.50");
  });

  it("keeps precision that a float would lose", () => {
    expect(formatBDT("9007199254740993.25")).toBe("৳9,00,71,99,25,47,40,993.25");
  });

  it("puts the minus sign before the taka sign", () => {
    expect(formatBDT("-1500")).toBe("-৳1,500.00");
  });

  it("uses Bangla digits when asked", () => {
    expect(formatBDT("304.2", { digits: "bn" })).toBe("৳৩০৪.২০");
  });
});

describe("formatCompactBDT", () => {
  it("leaves amounts under one lakh in full", () => {
    expect(formatCompactBDT("99999")).toBe("৳99,999.00");
  });

  it("uses lakh and crore", () => {
    expect(formatCompactBDT("1235000")).toBe("৳12.35 lakh");
    expect(formatCompactBDT("32000000")).toBe("৳3.2 crore");
    expect(formatCompactBDT("-500000")).toBe("-৳5 lakh");
  });

  it("uses Bangla unit names and digits", () => {
    expect(formatCompactBDT("1235000", { language: "bn", digits: "bn" })).toBe("৳১২.৩৫ লাখ");
    expect(formatCompactBDT("32000000", { language: "bn", digits: "bn" })).toBe("৳৩.২ কোটি");
  });
});

describe("formatPercent", () => {
  it("formats a value already in percent", () => {
    expect(formatPercent("4.42")).toBe("4.42%");
    expect(formatPercent(-4.42, { signed: true })).toBe("-4.42%");
    expect(formatPercent(7.65, { signed: true, fractionDigits: 1 })).toBe("+7.7%");
    expect(formatPercent("7.65", { digits: "bn" })).toBe("৭.৬৫%");
  });
});

describe("formatDate", () => {
  it("shows a calendar date unchanged", () => {
    expect(formatDate("2026-11-12")).toBe("12 Nov 2026");
  });

  it("converts an instant to Asia/Dhaka", () => {
    // 20:30 UTC on the 12th is 02:30 on the 13th in Dhaka.
    expect(formatDate("2026-11-12T20:30:00Z")).toBe("13 Nov 2026");
  });

  it("adds 24-hour Dhaka time when asked", () => {
    expect(formatDate("2026-11-12T11:30:00Z", { withTime: true })).toBe("12 Nov 2026, 17:30");
    const bangla = formatDate("2026-11-12T11:30:00Z", { language: "bn", digits: "bn", withTime: true });
    expect(bangla).toContain("১৭:৩০");
    expect(bangla).not.toMatch(/[AP]M/i);
  });

  it("formats in Bangla with Bangla digits", () => {
    const text = formatDate("2026-11-12", { language: "bn", digits: "bn" });
    expect(text).toContain("১২");
    expect(text).toContain("২০২৬");
  });

  it("rejects an invalid date", () => {
    expect(() => formatDate("not a date")).toThrow(RangeError);
  });
});
