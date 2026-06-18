from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, Course
from organizations.models import Organization
from memberships.models import Membership
from elections.models import Election, ElectionPosition, ElectionVoter, Candidate, Vote
from elections.utils import is_election_manager, compute_voter_pool, get_vote_tally


def make_user(student_id, email=None):
    return User.objects.create_user(
        email=email or f'{student_id}@universityofbohol.edu.ph',
        password='testpass',
        first_name='Test',
        last_name='User',
        student_id=student_id,
        is_active=True,
        is_email_verified=True,
    )


def make_org(name='Test Org', is_cso=False):
    return Organization.objects.create(name=name, status='active', is_cso=is_cso)


def make_election(org, status='draft'):
    now = timezone.now()
    return Election.objects.create(
        organization=org,
        title='Test Election',
        status=status,
        start_datetime=now,
        end_datetime=now + timedelta(hours=2),
    )


# ─── is_election_manager ─────────────────────────────────────────────────────

class IsElectionManagerTests(TestCase):

    def setUp(self):
        self.org = make_org()
        self.chairman = make_user('001')
        self.co_chairman = make_user('002')
        self.officer = make_user('003')
        self.member = make_user('004')

        Membership.objects.create(user=self.chairman, organization=self.org, role='chairman', status='active')
        Membership.objects.create(user=self.co_chairman, organization=self.org, role='co_chairman', status='active')
        Membership.objects.create(user=self.officer, organization=self.org, role='officer', status='active')
        Membership.objects.create(user=self.member, organization=self.org, role='member', status='active')

    def test_chairman_is_manager(self):
        self.assertTrue(is_election_manager(self.chairman, self.org))

    def test_co_chairman_is_manager(self):
        self.assertTrue(is_election_manager(self.co_chairman, self.org))

    def test_officer_is_not_manager(self):
        self.assertFalse(is_election_manager(self.officer, self.org))

    def test_member_is_not_manager(self):
        self.assertFalse(is_election_manager(self.member, self.org))

    def test_inactive_membership_not_manager(self):
        inactive = make_user('005')
        Membership.objects.create(user=inactive, organization=self.org, role='chairman', status='left')
        self.assertFalse(is_election_manager(inactive, self.org))

    def test_unauthenticated_user_not_manager(self):
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(is_election_manager(anon, self.org))


# ─── compute_voter_pool ───────────────────────────────────────────────────────

class ComputeVoterPoolTests(TestCase):

    def setUp(self):
        self.org = make_org()
        self.other_org = make_org('Other Org')
        self.election = make_election(self.org)

        self.member1 = make_user('101')
        self.member2 = make_user('102')
        self.officer1 = make_user('103')
        self.chairman1 = make_user('104')
        self.other_chairman = make_user('105')
        self.inactive_user = make_user('106')
        self.inactive_user.is_active = False
        self.inactive_user.save()

        Membership.objects.create(user=self.member1, organization=self.org, role='member', status='active')
        Membership.objects.create(user=self.member2, organization=self.org, role='member', status='active')
        Membership.objects.create(user=self.officer1, organization=self.org, role='officer', status='active')
        Membership.objects.create(user=self.chairman1, organization=self.org, role='chairman', status='active')
        Membership.objects.create(user=self.other_chairman, organization=self.other_org, role='chairman', status='active')

    def test_empty_pool_when_no_criteria(self):
        pool = compute_voter_pool(self.election)
        self.assertEqual(pool.count(), 0)

    def test_voters_org_members_includes_all_roles(self):
        self.election.voters_org_members = True
        self.election.save()
        pool = compute_voter_pool(self.election)
        self.assertIn(self.member1, pool)
        self.assertIn(self.officer1, pool)
        self.assertIn(self.chairman1, pool)
        self.assertNotIn(self.other_chairman, pool)

    def test_voters_org_officers_excludes_members(self):
        self.election.voters_org_officers = True
        self.election.save()
        pool = compute_voter_pool(self.election)
        self.assertIn(self.officer1, pool)
        self.assertIn(self.chairman1, pool)
        self.assertNotIn(self.member1, pool)

    def test_voters_all_chairmen_across_orgs(self):
        self.election.voters_all_chairmen = True
        self.election.save()
        pool = compute_voter_pool(self.election)
        self.assertIn(self.chairman1, pool)
        self.assertIn(self.other_chairman, pool)
        self.assertNotIn(self.member1, pool)

    def test_deduplication_with_multiple_criteria(self):
        self.election.voters_org_members = True
        self.election.voters_org_officers = True
        self.election.save()
        pool = compute_voter_pool(self.election)
        # chairman1 matches both criteria — should appear once
        ids = list(pool.values_list('id', flat=True))
        self.assertEqual(ids.count(self.chairman1.id), 1)

    def test_inactive_users_excluded_from_all_students(self):
        self.election.voters_all_students = True
        self.election.save()
        pool = compute_voter_pool(self.election)
        self.assertNotIn(self.inactive_user, pool)


# ─── get_vote_tally ───────────────────────────────────────────────────────────

class GetVoteTallyTests(TestCase):

    def setUp(self):
        self.org = make_org()
        self.election = make_election(self.org, status='closed')
        self.position = ElectionPosition.objects.create(
            election=self.election, name='President', target_role='chairman'
        )
        self.voter1 = make_user('201')
        self.voter2 = make_user('202')
        self.voter3 = make_user('203')
        self.cand_a = Candidate.objects.create(election=self.election, position=self.position, user=self.voter1)
        self.cand_b = Candidate.objects.create(election=self.election, position=self.position, user=self.voter2)

    def test_tally_counts_votes_correctly(self):
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_a, voter=self.voter2)
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_a, voter=self.voter3)
        tally = get_vote_tally(self.election)
        pos_data = tally[str(self.position.id)]
        self.assertEqual(pos_data['candidates'][0]['count'], 2)
        self.assertEqual(pos_data['candidates'][0]['candidate_id'], self.cand_a.id)

    def test_tally_detects_tie(self):
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_a, voter=self.voter2)
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_b, voter=self.voter3)
        tally = get_vote_tally(self.election)
        self.assertTrue(tally[str(self.position.id)]['is_tied'])

    def test_tally_detects_no_contest(self):
        tally = get_vote_tally(self.election)
        self.assertTrue(tally[str(self.position.id)]['no_contest'])

    def test_tally_not_tied_with_clear_winner(self):
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_a, voter=self.voter2)
        Vote.objects.create(election=self.election, position=self.position, candidate=self.cand_a, voter=self.voter3)
        tally = get_vote_tally(self.election)
        self.assertFalse(tally[str(self.position.id)]['is_tied'])
        self.assertFalse(tally[str(self.position.id)]['no_contest'])


# ─── Vote uniqueness & permissions ───────────────────────────────────────────

class VotePermissionTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.org = make_org()
        self.election = make_election(self.org, status='open')
        self.position = ElectionPosition.objects.create(
            election=self.election, name='VP', target_role='officer'
        )
        self.voter = make_user('301')
        self.non_voter = make_user('302')
        self.cand_user = make_user('303')
        self.candidate = Candidate.objects.create(
            election=self.election, position=self.position, user=self.cand_user
        )
        ElectionVoter.objects.create(election=self.election, user=self.voter)

    def test_non_voter_cannot_access_vote_page(self):
        self.client.force_login(self.non_voter)
        response = self.client.get(f'/elections/{self.election.id}/vote/')
        self.assertEqual(response.status_code, 403)

    def test_voter_can_access_vote_page(self):
        self.client.force_login(self.voter)
        response = self.client.get(f'/elections/{self.election.id}/vote/')
        self.assertEqual(response.status_code, 200)

    def test_duplicate_vote_rejected_at_db_level(self):
        from django.db import IntegrityError
        Vote.objects.create(
            election=self.election, position=self.position,
            candidate=self.candidate, voter=self.voter
        )
        with self.assertRaises(IntegrityError):
            Vote.objects.create(
                election=self.election, position=self.position,
                candidate=self.candidate, voter=self.voter
            )

    def test_cannot_vote_on_closed_election(self):
        self.election.status = 'closed'
        self.election.save()
        self.client.force_login(self.voter)
        response = self.client.post(f'/elections/{self.election.id}/vote/', {
            f'position_{self.position.id}': self.candidate.id
        })
        self.assertEqual(Vote.objects.filter(election=self.election).count(), 0)


# ─── Status transition guards ─────────────────────────────────────────────────

class ElectionStatusTransitionTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.org = make_org()
        self.manager = make_user('401')
        Membership.objects.create(user=self.manager, organization=self.org, role='chairman', status='active')

    def test_cannot_open_already_open_election(self):
        election = make_election(self.org, status='open')
        self.client.force_login(self.manager)
        response = self.client.post(f'/elections/{election.id}/open/')
        election.refresh_from_db()
        self.assertEqual(election.status, 'open')

    def test_cannot_release_results_of_open_election(self):
        election = make_election(self.org, status='open')
        self.client.force_login(self.manager)
        response = self.client.post(f'/elections/{election.id}/release/')
        election.refresh_from_db()
        self.assertNotEqual(election.status, 'results_released')

    def test_cannot_close_draft_election(self):
        election = make_election(self.org, status='draft')
        self.client.force_login(self.manager)
        response = self.client.post(f'/elections/{election.id}/close/')
        election.refresh_from_db()
        self.assertEqual(election.status, 'draft')
