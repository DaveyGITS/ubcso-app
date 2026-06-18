/**
 * dashboard_filter.js
 * Pure sort/filter functions for the Member Management Dashboard.
 * These are extracted from members.html for testability.
 *
 * Member object shape: { role, year, lastName, firstName }
 *   role: 'chairman' | 'co_chairman' | 'officer' | 'member'
 *   year: number
 *   lastName: string
 *   firstName: string
 */

// Role rank map — lower number = higher rank
const ROLE_RANK = { chairman: 0, co_chairman: 1, officer: 2, member: 3 };

/**
 * Sort members by role rank ascending, then last name alphabetically.
 * @param {Array<{role: string, year: number, lastName: string, firstName: string}>} members
 * @returns {Array}
 */
function sortAll(members) {
    return [...members].sort((a, b) => {
        const rankA = ROLE_RANK[a.role] ?? Infinity;
        const rankB = ROLE_RANK[b.role] ?? Infinity;
        if (rankA !== rankB) return rankA - rankB;
        return (a.lastName || '').localeCompare(b.lastName || '');
    });
}

/**
 * Sort members by year level ascending, then last name, then first name.
 * @param {Array<{role: string, year: number, lastName: string, firstName: string}>} members
 * @returns {Array}
 */
function sortAlpha(members) {
    return [...members].sort((a, b) => {
        const yearA = a.year || 0;
        const yearB = b.year || 0;
        if (yearA !== yearB) return yearA - yearB;
        const lastCmp = (a.lastName || '').localeCompare(b.lastName || '');
        if (lastCmp !== 0) return lastCmp;
        return (a.firstName || '').localeCompare(b.firstName || '');
    });
}

/**
 * Filter to chairman/co_chairman/officer roles, then sort by rank then last name.
 * @param {Array<{role: string, year: number, lastName: string, firstName: string}>} members
 * @returns {Array}
 */
function sortOfficers(members) {
    const officerRoles = new Set(['chairman', 'co_chairman', 'officer']);
    return [...members]
        .filter(m => officerRoles.has(m.role))
        .sort((a, b) => {
            const rankA = ROLE_RANK[a.role] ?? Infinity;
            const rankB = ROLE_RANK[b.role] ?? Infinity;
            if (rankA !== rankB) return rankA - rankB;
            return (a.lastName || '').localeCompare(b.lastName || '');
        });
}

module.exports = { ROLE_RANK, sortAll, sortAlpha, sortOfficers };
