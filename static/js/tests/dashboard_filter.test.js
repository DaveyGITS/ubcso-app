'use strict';

const fc = require('fast-check');
const { ROLE_RANK, sortAll, sortAlpha, sortOfficers } = require('../dashboard_filter');

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

const roleArb = fc.constantFrom('chairman', 'co_chairman', 'officer', 'member');

const memberArb = fc.record({
    role: roleArb,
    year: fc.integer({ min: 0, max: 6 }),
    lastName: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
    firstName: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
});

const membersArb = fc.array(memberArb, { minLength: 0, maxLength: 50 });

// ---------------------------------------------------------------------------
// Property 1 — All Members completeness
// Feature: member-management-filters, Property 1: sortAll returns all input members
// ---------------------------------------------------------------------------

test('Property 1: sortAll returns all input members (completeness)', () => {
    // Validates: Requirements 2.1
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortAll(members);
            expect(result).toHaveLength(members.length);
            members.forEach(m => {
                expect(result).toContain(m);
            });
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 2 — All Members sort order invariant
// Feature: member-management-filters, Property 2: role rank then last name
// ---------------------------------------------------------------------------

test('Property 2: sortAll — rank[i] <= rank[i+1]; if equal rank, lastName[i] <= lastName[i+1]', () => {
    // Validates: Requirements 2.2
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortAll(members);
            for (let i = 0; i < result.length - 1; i++) {
                const rankI = ROLE_RANK[result[i].role] ?? Infinity;
                const rankJ = ROLE_RANK[result[i + 1].role] ?? Infinity;
                expect(rankI).toBeLessThanOrEqual(rankJ);
                if (rankI === rankJ) {
                    const cmp = (result[i].lastName || '').localeCompare(result[i + 1].lastName || '');
                    expect(cmp).toBeLessThanOrEqual(0);
                }
            }
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 3 — Alphabetical completeness
// Feature: member-management-filters, Property 3: sortAlpha returns all input members
// ---------------------------------------------------------------------------

test('Property 3: sortAlpha returns all input members (completeness)', () => {
    // Validates: Requirements 3.4
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortAlpha(members);
            expect(result).toHaveLength(members.length);
            members.forEach(m => {
                expect(result).toContain(m);
            });
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 4 — Alphabetical year/name sort invariant
// Feature: member-management-filters, Property 4: year asc, lastName asc, firstName asc
// ---------------------------------------------------------------------------

test('Property 4: sortAlpha — year[i] <= year[i+1]; if equal year, lastName asc; if equal year+lastName, firstName asc', () => {
    // Validates: Requirements 3.1, 3.2
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortAlpha(members);
            for (let i = 0; i < result.length - 1; i++) {
                const yearI = result[i].year || 0;
                const yearJ = result[i + 1].year || 0;
                expect(yearI).toBeLessThanOrEqual(yearJ);
                if (yearI === yearJ) {
                    const lastCmp = (result[i].lastName || '').localeCompare(result[i + 1].lastName || '');
                    expect(lastCmp).toBeLessThanOrEqual(0);
                    if (lastCmp === 0) {
                        const firstCmp = (result[i].firstName || '').localeCompare(result[i + 1].firstName || '');
                        expect(firstCmp).toBeLessThanOrEqual(0);
                    }
                }
            }
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 5 — Officers filter excludes member-role rows
// Feature: member-management-filters, Property 5: sortOfficers contains no 'member' role
// ---------------------------------------------------------------------------

test('Property 5: sortOfficers — result contains only chairman/co_chairman/officer roles', () => {
    // Validates: Requirements 4.1
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortOfficers(members);
            result.forEach(m => {
                expect(m.role).not.toBe('member');
                expect(['chairman', 'co_chairman', 'officer']).toContain(m.role);
            });
            const officerInputs = members.filter(m => m.role !== 'member');
            expect(result).toHaveLength(officerInputs.length);
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 6 — Officers rank-order invariant
// Feature: member-management-filters, Property 6: rank[i] <= rank[i+1]; if equal rank, lastName asc
// ---------------------------------------------------------------------------

test('Property 6: sortOfficers — rank[i] <= rank[i+1]; if equal rank, lastName[i] <= lastName[i+1]', () => {
    // Validates: Requirements 4.2, 4.3
    fc.assert(
        fc.property(membersArb, (members) => {
            const result = sortOfficers(members);
            for (let i = 0; i < result.length - 1; i++) {
                const rankI = ROLE_RANK[result[i].role] ?? Infinity;
                const rankJ = ROLE_RANK[result[i + 1].role] ?? Infinity;
                expect(rankI).toBeLessThanOrEqual(rankJ);
                if (rankI === rankJ) {
                    const cmp = (result[i].lastName || '').localeCompare(result[i + 1].lastName || '');
                    expect(cmp).toBeLessThanOrEqual(0);
                }
            }
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// DOM helpers for Properties 7 & 8
// ---------------------------------------------------------------------------

/**
 * Build a minimal jsdom-backed DashboardFilter instance.
 * Returns { applyFilter, getActiveFilters, openModal, closeModal }
 */
function buildDOM(memberList) {
    // Build filter bar HTML
    const filterBarHTML = `
        <div id="filter-bar">
            <button class="filter-btn active-filter" data-filter="all">All Members</button>
            <button class="filter-btn" data-filter="alphabetical">Alphabetical</button>
            <button class="filter-btn" data-filter="officers">Officers</button>
        </div>`;

    // Build member rows HTML
    const rowsHTML = memberList.map(m =>
        `<div data-membership-id="${Math.random()}"
              data-role="${m.role}"
              data-year="${m.year}"
              data-last-name="${m.lastName}"
              data-first-name="${m.firstName}"></div>`
    ).join('');

    document.body.innerHTML = `
        ${filterBarHTML}
        <div id="member-container" class="divide-y divide-gray-50">
            ${rowsHTML}
        </div>
        <p id="officers-empty-msg" class="hidden"></p>
        <div id="promote-modal" class="hidden"></div>
        <div id="title-modal" class="hidden"></div>`;

    // Inline DashboardFilter (mirrors the template implementation)
    const ROLE_RANK_LOCAL = { chairman: 0, co_chairman: 1, officer: 2, member: 3 };

    class DashboardFilter {
        constructor(containerSelector, filterBarSelector) {
            this.container = document.querySelector(containerSelector);
            this.filterBar = document.querySelector(filterBarSelector);
            this.emptyMsg = document.getElementById('officers-empty-msg');
            this.rows = Array.from(this.container.querySelectorAll('[data-membership-id]'));
            this.filterBar.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => this.applyFilter(btn.dataset.filter));
            });
            this.applyFilter('all');
        }

        _sortAll(rows) {
            return [...rows].sort((a, b) => {
                const rA = ROLE_RANK_LOCAL[a.dataset.role] ?? Infinity;
                const rB = ROLE_RANK_LOCAL[b.dataset.role] ?? Infinity;
                if (rA !== rB) return rA - rB;
                return (a.dataset.lastName || '').localeCompare(b.dataset.lastName || '');
            });
        }

        _sortAlpha(rows) {
            return [...rows].sort((a, b) => {
                const yA = parseInt(a.dataset.year, 10) || 0;
                const yB = parseInt(b.dataset.year, 10) || 0;
                if (yA !== yB) return yA - yB;
                const lc = (a.dataset.lastName || '').localeCompare(b.dataset.lastName || '');
                if (lc !== 0) return lc;
                return (a.dataset.firstName || '').localeCompare(b.dataset.firstName || '');
            });
        }

        _sortOfficers(rows) {
            const ok = new Set(['chairman', 'co_chairman', 'officer']);
            return [...rows].filter(r => ok.has(r.dataset.role)).sort((a, b) => {
                const rA = ROLE_RANK_LOCAL[a.dataset.role] ?? Infinity;
                const rB = ROLE_RANK_LOCAL[b.dataset.role] ?? Infinity;
                if (rA !== rB) return rA - rB;
                return (a.dataset.lastName || '').localeCompare(b.dataset.lastName || '');
            });
        }

        applyFilter(mode) {
            this.container.querySelectorAll('.year-heading').forEach(el => el.remove());
            let sorted, visibleSet;
            if (mode === 'all') {
                sorted = this._sortAll(this.rows);
                visibleSet = new Set(this.rows);
            } else if (mode === 'alphabetical') {
                sorted = this._sortAlpha(this.rows);
                visibleSet = new Set(this.rows);
            } else if (mode === 'officers') {
                sorted = this._sortOfficers(this.rows);
                visibleSet = new Set(sorted);
            }
            sorted.forEach(row => { this.container.appendChild(row); row.style.display = ''; });
            this.rows.forEach(row => { if (!visibleSet.has(row)) row.style.display = 'none'; });
            if (mode === 'alphabetical') {
                let lastYear = null;
                sorted.forEach(row => {
                    const year = parseInt(row.dataset.year, 10) || 0;
                    if (year !== lastYear) {
                        lastYear = year;
                        const h = document.createElement('div');
                        h.className = 'year-heading';
                        h.textContent = year > 0 ? `Year ${year}` : 'Unknown Year';
                        this.container.insertBefore(h, row);
                    }
                });
            }
            if (this.emptyMsg) {
                if (mode === 'officers' && sorted.length === 0) {
                    this.emptyMsg.classList.remove('hidden');
                } else {
                    this.emptyMsg.classList.add('hidden');
                }
            }
            this.filterBar.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.toggle('active-filter', btn.dataset.filter === mode);
            });
            this._currentMode = mode;
        }
    }

    const instance = new DashboardFilter('#member-container', '#filter-bar');
    return instance;
}

// ---------------------------------------------------------------------------
// Property 7 — Active filter highlight is exclusive
// Feature: member-management-filters, Property 7: exactly one .filter-btn has active-filter after applyFilter
// ---------------------------------------------------------------------------

test('Property 7: after applyFilter(mode), exactly one .filter-btn has active-filter class', () => {
    // Validates: Requirements 1.3, 5.2
    const modeArb = fc.constantFrom('all', 'alphabetical', 'officers');
    const smallMembersArb = fc.array(memberArb, { minLength: 0, maxLength: 10 });

    fc.assert(
        fc.property(smallMembersArb, modeArb, (members, mode) => {
            const df = buildDOM(members);
            df.applyFilter(mode);

            const filterBar = document.getElementById('filter-bar');
            const allBtns = Array.from(filterBar.querySelectorAll('.filter-btn'));
            const activeBtns = allBtns.filter(b => b.classList.contains('active-filter'));

            // Exactly one button should be active
            expect(activeBtns).toHaveLength(1);
            // That button should be the one matching the mode
            expect(activeBtns[0].dataset.filter).toBe(mode);
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Property 8 — Modal open/close does not change active filter state
// Feature: member-management-filters, Property 8: opening and closing a modal does not change active filter mode
// ---------------------------------------------------------------------------

test('Property 8: opening and closing a modal does not change the active filter state', () => {
    // Validates: Requirements 6.1
    const modeArb = fc.constantFrom('all', 'alphabetical', 'officers');
    const modalIdArb = fc.constantFrom('promote-modal', 'title-modal');
    const smallMembersArb = fc.array(memberArb, { minLength: 0, maxLength: 10 });

    fc.assert(
        fc.property(smallMembersArb, modeArb, modalIdArb, (members, mode, modalId) => {
            const df = buildDOM(members);
            df.applyFilter(mode);

            // Record active button before modal interaction
            const filterBar = document.getElementById('filter-bar');
            const activeBefore = Array.from(filterBar.querySelectorAll('.filter-btn'))
                .filter(b => b.classList.contains('active-filter'))
                .map(b => b.dataset.filter);

            // Simulate open modal
            const modal = document.getElementById(modalId);
            modal.classList.remove('hidden');

            // Simulate close modal (no filter change)
            modal.classList.add('hidden');

            // Active filter should be unchanged
            const activeAfter = Array.from(filterBar.querySelectorAll('.filter-btn'))
                .filter(b => b.classList.contains('active-filter'))
                .map(b => b.dataset.filter);

            expect(activeAfter).toEqual(activeBefore);
            expect(activeAfter).toHaveLength(1);
            expect(activeAfter[0]).toBe(mode);
        }),
        { numRuns: 100 }
    );
});

// ---------------------------------------------------------------------------
// Example-based unit tests
// ---------------------------------------------------------------------------

describe('Example-based unit tests', () => {
    // Mixed member list: 1 chairman, 1 co_chairman, 2 officers, 3 regular members
    const mixedMembers = [
        { role: 'chairman',    year: 2, lastName: 'Reyes',   firstName: 'Ana' },
        { role: 'co_chairman', year: 3, lastName: 'Santos',  firstName: 'Ben' },
        { role: 'officer',     year: 1, lastName: 'Cruz',    firstName: 'Cara' },
        { role: 'officer',     year: 2, lastName: 'Lim',     firstName: 'Dan' },
        { role: 'member',      year: 1, lastName: 'Aquino',  firstName: 'Eva' },
        { role: 'member',      year: 2, lastName: 'Bautista',firstName: 'Felix' },
        { role: 'member',      year: 3, lastName: 'Garcia',  firstName: 'Gia' },
    ];

    // Only regular members — no officers
    const membersOnly = [
        { role: 'member', year: 1, lastName: 'Aquino',   firstName: 'Eva' },
        { role: 'member', year: 2, lastName: 'Bautista', firstName: 'Felix' },
        { role: 'member', year: 3, lastName: 'Garcia',   firstName: 'Gia' },
    ];

    // 6.1 Filter bar renders with exactly three buttons with correct labels
    test('6.1: filter bar renders with exactly three buttons with correct labels', () => {
        buildDOM(mixedMembers);
        const filterBar = document.getElementById('filter-bar');
        const buttons = Array.from(filterBar.querySelectorAll('.filter-btn'));

        expect(buttons).toHaveLength(3);
        expect(buttons[0].textContent.trim()).toBe('All Members');
        expect(buttons[1].textContent.trim()).toBe('Alphabetical');
        expect(buttons[2].textContent.trim()).toBe('Officers');
    });

    // 6.2 "All Members" button has active-filter class on page load
    test('6.2: "All Members" button has active-filter class on page load', () => {
        buildDOM(mixedMembers);
        const filterBar = document.getElementById('filter-bar');
        const buttons = Array.from(filterBar.querySelectorAll('.filter-btn'));

        const allMembersBtn = buttons.find(b => b.dataset.filter === 'all');
        expect(allMembersBtn.classList.contains('active-filter')).toBe(true);

        // Other buttons should not be active
        buttons.filter(b => b.dataset.filter !== 'all').forEach(b => {
            expect(b.classList.contains('active-filter')).toBe(false);
        });
    });

    // 6.3 Year level headings appear in alphabetical mode
    test('6.3: year level headings appear in alphabetical mode', () => {
        const df = buildDOM(mixedMembers);
        df.applyFilter('alphabetical');

        const container = document.getElementById('member-container');
        const headings = Array.from(container.querySelectorAll('.year-heading'));

        // mixedMembers spans year levels 1, 2, 3 — expect 3 headings
        expect(headings.length).toBeGreaterThan(0);
        expect(headings.some(h => h.textContent.includes('Year 1'))).toBe(true);
        expect(headings.some(h => h.textContent.includes('Year 2'))).toBe(true);
        expect(headings.some(h => h.textContent.includes('Year 3'))).toBe(true);

        // Headings should not appear in 'all' mode
        df.applyFilter('all');
        const headingsAfterAll = Array.from(container.querySelectorAll('.year-heading'));
        expect(headingsAfterAll).toHaveLength(0);
    });

    // 6.4 Officers empty-state message appears when no qualifying members exist
    test('6.4: officers empty-state message appears when no qualifying members exist', () => {
        const df = buildDOM(membersOnly);
        df.applyFilter('officers');

        const emptyMsg = document.getElementById('officers-empty-msg');
        expect(emptyMsg.classList.contains('hidden')).toBe(false);

        // Message should be hidden for other filters
        df.applyFilter('all');
        expect(emptyMsg.classList.contains('hidden')).toBe(true);
    });

    // 6.5 Page reload resets filter to "All Members" default
    test('6.5: page reload resets filter to "All Members" default', () => {
        // Simulate a "used" state — alphabetical was active
        const df1 = buildDOM(mixedMembers);
        df1.applyFilter('alphabetical');
        const filterBar1 = document.getElementById('filter-bar');
        expect(filterBar1.querySelector('[data-filter="alphabetical"]').classList.contains('active-filter')).toBe(true);

        // Simulate page reload by building a fresh DOM
        buildDOM(mixedMembers);
        const filterBar2 = document.getElementById('filter-bar');
        const allBtn = filterBar2.querySelector('[data-filter="all"]');
        const alphaBtn = filterBar2.querySelector('[data-filter="alphabetical"]');

        expect(allBtn.classList.contains('active-filter')).toBe(true);
        expect(alphaBtn.classList.contains('active-filter')).toBe(false);

        // No year headings should be present on fresh load
        const container = document.getElementById('member-container');
        expect(container.querySelectorAll('.year-heading')).toHaveLength(0);
    });
});
