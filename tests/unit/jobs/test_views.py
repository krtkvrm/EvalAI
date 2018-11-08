import collections
import os
import shutil

from datetime import timedelta

from django.core.urlresolvers import reverse_lazy
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils import timezone

from allauth.account.models import EmailAddress
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from challenges.models import (Challenge,
                               ChallengePhase,
                               ChallengePhaseSplit,
                               DatasetSplit,
                               Leaderboard,
                               LeaderboardData)
from hosts.models import ChallengeHostTeam, ChallengeHost
from jobs.models import Submission
from participants.models import ParticipantTeam, Participant


class BaseAPITestClass(APITestCase):

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

        self.user = User.objects.create(
            username='someuser',
            email="user@test.com",
            password='secret_password')

        EmailAddress.objects.create(
            user=self.user,
            email='user@test.com',
            primary=True,
            verified=True)

        self.user1 = User.objects.create(
            username='someuser1',
            email="user1@test.com",
            password='secret_password1')

        EmailAddress.objects.create(
            user=self.user1,
            email='user1@test.com',
            primary=True,
            verified=True)

        self.challenge_host_team = ChallengeHostTeam.objects.create(
            team_name='Test Challenge Host Team',
            created_by=self.user)

        self.challenge_host = ChallengeHost.objects.create(
            user=self.user,
            team_name=self.challenge_host_team,
            status=ChallengeHost.ACCEPTED,
            permissions=ChallengeHost.ADMIN
        )

        self.host_participant_team = ParticipantTeam.objects.create(
            team_name='Host Participant Team for Challenge',
            created_by=self.user
        )

        self.host_participant = Participant.objects.create(
            user=self.user,
            status=Participant.SELF,
            team=self.host_participant_team
        )

        self.participant_team = ParticipantTeam.objects.create(
            team_name='Participant Team for Challenge',
            created_by=self.user1)

        self.participant = Participant.objects.create(
            user=self.user1,
            status=Participant.SELF,
            team=self.participant_team)

        self.challenge = Challenge.objects.create(
            title='Test Challenge',
            description='Description for test challenge',
            terms_and_conditions='Terms and conditions for test challenge',
            submission_guidelines='Submission guidelines for test challenge',
            creator=self.challenge_host_team,
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() + timedelta(days=1),
            published=False,
            enable_forum=True,
            anonymous_leaderboard=False)

        self.leaderboard_schema = {
            'labels': ['score', 'test-score'],
            'default_order_by': 'score'
        }
        self.leaderboard = Leaderboard.objects.create(
            schema=self.leaderboard_schema
        )

        self.private_leaderboard = Leaderboard.objects.create(
            schema=self.leaderboard_schema
        )

        self.challenge.participant_teams.add(self.host_participant_team)

        try:
            os.makedirs('/tmp/evalai')
        except OSError:
            pass

        with self.settings(MEDIA_ROOT='/tmp/evalai'):
            self.challenge_phase = ChallengePhase.objects.create(
                name='Challenge Phase',
                description='Description for Challenge Phase',
                leaderboard_public=False,
                max_submissions_per_day=10,
                max_submissions_per_month=20,
                max_submissions=100,
                is_public=True,
                start_date=timezone.now() - timedelta(days=2),
                end_date=timezone.now() + timedelta(days=1),
                challenge=self.challenge,
                test_annotation=SimpleUploadedFile('test_sample_file.txt',
                                                   b'Dummy file content', content_type='text/plain'),
                codename='Phase Code name'
            )

            self.private_challenge_phase = ChallengePhase.objects.create(
                name='Private Challenge Phase',
                description='Description for Private Challenge Phase',
                leaderboard_public=False,
                max_submissions_per_day=10,
                max_submissions=100,
                is_public=False,
                start_date=timezone.now() - timedelta(days=2),
                end_date=timezone.now() + timedelta(days=1),
                challenge=self.challenge,
                test_annotation=SimpleUploadedFile('test_sample_file.txt',
                                                   b'Dummy file content', content_type='text/plain'),
                codename='Private Phase Code name'
            )

        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.client.force_authenticate(user=self.user1)

        self.input_file = SimpleUploadedFile(
            "dummy_input.txt", b"file_content", content_type="text/plain")

    def tearDown(self):
        shutil.rmtree('/tmp/evalai')

    def test_challenge_submission_when_challenge_does_not_exist(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.delete()

        expected = {
            'error': 'Challenge does not exist'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_challenge_submission_when_challenge_is_not_active(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.end_date = timezone.now() - timedelta(days=1)
        self.challenge.save()

        expected = {
            'error': 'Challenge is not active'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_challenge_submission_when_challenge_phase_does_not_exist(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge_phase.delete()

        expected = {
            'error': 'Challenge Phase does not exist'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_challenge_submission_when_challenge_phase_is_not_public(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge_phase.is_public = False
        self.challenge_phase.save()

        expected = {
            'error': 'Sorry, cannot accept submissions since challenge phase is not public'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_challenge_submission_when_challenge_phase_is_private_and_user_is_host(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge_phase.is_public = False
        self.challenge_phase.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_challenge_submission_when_challenge_phase_is_private_and_user_is_not_host(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge_phase.is_public = False
        self.challenge_phase.save()

        expected = {
            'error': 'Sorry, cannot accept submissions since challenge phase is not public'
        }

        self.client.force_authenticate(user=self.user1)

        response = self.client.post(self.url, {
            'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_challenge_submission_when_participant_team_is_none(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.participant_team.delete()

        expected = {
            'error': 'You haven\'t participated in the challenge'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_challenge_submission_when_participant_team_hasnt_participated_in_challenge(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        # Note that we haven't added the self.participant_team to Challenge
        expected = {
            'error': 'You haven\'t participated in the challenge'
        }

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_challenge_submission_when_status_and_file_is_not_submitted(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()

        expected = {
            'status': ['This field is required.'],
            'input_file': ['No file was submitted.']
        }

        response = self.client.post(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_challenge_submission_when_form_encoding_is_wrong(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()

        expected = {
            'input_file': ['The submitted data was not a file. Check the encoding type on the form.']
        }

        response = self.client.post(
            self.url, {'status': 'submitting', 'input_file': self.input_file})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_challenge_submission_when_status_is_not_correct(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()

        expected = {
            'status': ['"XYZ" is not a valid choice.']
        }

        response = self.client.post(
            self.url, {'status': 'XYZ', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)

    def test_challenge_submission_for_successful_submission(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()

        response = self.client.post(self.url, {
                                    'status': 'submitting', 'input_file': self.input_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class GetChallengeSubmissionTest(BaseAPITestClass):

    def setUp(self):
        super(GetChallengeSubmissionTest, self).setUp()
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.submission = Submission.objects.create(
            participant_team=self.participant_team,
            challenge_phase=self.challenge_phase,
            created_by=self.challenge_host_team.created_by,
            status='submitted',
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/",
            is_public=True,
        )

    def test_challenge_submission_when_challenge_does_not_exist(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge.delete()

        expected = {
            'error': 'Challenge does not exist'
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_challenge_submission_when_challenge_phase_does_not_exist(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.challenge_phase.delete()

        expected = {
            'error': 'Challenge Phase does not exist'
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_challenge_submission_when_participant_team_is_none(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        self.participant_team.delete()

        expected = {
            'error': 'You haven\'t participated in the challenge'
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_challenge_submission_when_participant_team_hasnt_participated_in_challenge(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})

        # Note that we haven't added the self.participant_team to Challenge
        expected = {
            'error': 'You haven\'t participated in the challenge'
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_challenge_submissions(self):
        self.url = reverse_lazy('jobs:challenge_submission',
                                kwargs={'challenge_id': self.challenge.pk,
                                        'challenge_phase_id': self.challenge_phase.pk})
        expected = [
            {
                'id': self.submission.id,
                'participant_team': self.submission.participant_team.pk,
                'participant_team_name': self.submission.participant_team.team_name,
                'execution_time': self.submission.execution_time,
                'challenge_phase': self.submission.challenge_phase.pk,
                'created_by': self.submission.created_by.pk,
                'status': self.submission.status,
                'input_file': "http://testserver%s" % (self.submission.input_file.url),
                'method_name': self.submission.method_name,
                'method_description': self.submission.method_description,
                'project_url': self.submission.project_url,
                'publication_url': self.submission.publication_url,
                'stdout_file': None,
                'stderr_file': None,
                'submission_result_file': None,
                "submitted_at": "{0}{1}".format(self.submission.submitted_at.isoformat(), 'Z').replace("+00:00", ""),
                "is_public": self.submission.is_public,
                "when_made_public": self.submission.when_made_public,
            }
        ]
        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()
        response = self.client.get(self.url, {})
        self.assertEqual(response.data['results'], expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class GetRemainingSubmissionTest(BaseAPITestClass):

    def setUp(self):
        super(GetRemainingSubmissionTest, self).setUp()
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_id': self.challenge_phase.pk,
                                        'challenge_id': self.challenge.pk})

        self.submission1 = Submission.objects.create(
            participant_team=self.participant_team,
            challenge_phase=self.challenge_phase,
            created_by=self.challenge_host_team.created_by,
            status='submitted',
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/",
            is_public=True,
        )

        self.submission2 = Submission.objects.create(
            participant_team=self.participant_team,
            challenge_phase=self.challenge_phase,
            created_by=self.challenge_host_team.created_by,
            status='failed',
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/",
            is_public=True,
        )

    def test_get_remaining_submission_when_challenge_does_not_exist(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk+1})

        expected = {
            'detail': 'Challenge {} does not exist'.format(self.challenge.pk+1)
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_remaining_submission_when_challenge_phase_does_not_exist(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk + 2,
                                        'challenge_pk': self.challenge.pk})

        expected = {
            'detail': 'ChallengePhase {} does not exist'.format(self.challenge_phase.pk + 2)
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_remaining_submission_when_participant_team_hasnt_participated_in_challenge(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk})

        expected = {
            'error': 'You haven\'t participated in the challenge'
        }

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_remaining_submission_when_submission_made_three_days_back(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk})
        expected = {
            'remaining_submissions_today_count': 9,
            'remaining_submissions_this_month_count': 18,
            'remaining_submissions': 98
        }

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()
        self.submission1.submitted_at = timezone.now() - timedelta(days=3)
        self.submission1.save()
        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_remaining_submission_when__submission_made_today(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk})
        expected = {
            'remaining_submissions_today_count': 8,
            'remaining_submissions_this_month_count': 18,
            'remaining_submissions': 98
        }

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()
        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_remaining_submission_when_today_submissions_is_more_than_max_submissions(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk})

        """
        The value of max_submissions_per_day and max_submissions is set explicitly in order to test for a corner case
        in which max_submissions_per_day > max_submissions.
        """
        setattr(self.challenge_phase, 'max_submissions_per_day', 9)
        setattr(self.challenge_phase, 'max_submissions', 5)
        self.challenge_phase.save()

        failed_submissions = Submission.objects.filter(challenge_phase=self.challenge_phase,
                                                       challenge_phase__challenge=self.challenge,
                                                       status='failed').count()
        other_submissions = Submission.objects.filter(challenge_phase=self.challenge_phase,
                                                      challenge_phase__challenge=self.challenge).count()

        submission_count = self.challenge_phase.max_submissions - other_submissions - failed_submissions

        expected = {
            'remaining_submissions_today_count': submission_count,
            'remaining_submissions_this_month_count': submission_count,
            'remaining_submissions': submission_count
        }
        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()
        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_remaining_submission_time_when_limit_is_exhausted(self):
        self.url = reverse_lazy('jobs:get_remaining_submissions',
                                kwargs={'challenge_phase_pk': self.challenge_phase.pk,
                                        'challenge_pk': self.challenge.pk})
        setattr(self.challenge_phase, 'max_submissions_per_day', 1)
        self.challenge_phase.save()

        expected = {
            'message': 'You have exhausted today\'s submission limit',
        }

        self.challenge.participant_teams.add(self.participant_team)
        self.challenge.save()
        response = self.client.get(self.url, {})
        self.assertEqual(response.data['message'], expected['message'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ChangeSubmissionDataAndVisibilityTest(BaseAPITestClass):

    def setUp(self):
        super(ChangeSubmissionDataAndVisibilityTest, self).setUp()

        self.submission = Submission.objects.create(
            participant_team=self.participant_team,
            challenge_phase=self.challenge_phase,
            created_by=self.challenge_host_team.created_by,
            status='submitted',
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/",
            is_public=True,
            when_made_public=timezone.now()
        )

        self.private_submission = Submission.objects.create(
            participant_team=self.host_participant_team,
            challenge_phase=self.private_challenge_phase,
            created_by=self.challenge_host_team.created_by,
            status='submitted',
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/",
            is_public=True,
            when_made_public=timezone.now()
        )

        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

    def test_change_submission_data_and_visibility_when_challenge_does_not_exist(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk+10,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

        expected = {
            'detail': 'Challenge {} does not exist'.format(self.challenge.pk+10)
        }

        response = self.client.patch(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_change_submission_data_and_visibility_when_challenge_phase_does_not_exist(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk+10,
                                        'submission_pk': self.submission.pk})

        expected = {
            'detail': 'ChallengePhase {} does not exist'.format(self.challenge_phase.pk+10)
        }

        response = self.client.patch(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_change_submission_data_and_visibility_when_challenge_is_not_active(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})
        self.data = {
            'method_name': 'Updated Method Name'
        }
        self.challenge.end_date = timezone.now() - timedelta(days=1)
        self.challenge.save()

        expected = {
            'error': 'Challenge is not active'
        }
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_submission_data_and_visibility_when_challenge_is_not_public(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

        self.challenge_phase.is_public = False
        self.challenge_phase.save()
        self.data = {
            'method_name': 'Updated Method Name'
        }

        expected = {
            'error': 'Sorry, cannot accept submissions since challenge phase is not public'
        }

        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_submission_data_and_visibility_when_participant_team_is_none(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

        self.participant_team.delete()

        expected = {
            'error': 'You haven\'t participated in the challenge'
        }
        self.data = {
            'method_name': 'Updated Method Name'
        }

        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_submission_data_and_visibility_when_participant_team_hasnt_participated_in_challenge(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

        # Note that we haven't added the self.participant_team to Challenge
        expected = {
            'error': 'You haven\'t participated in the challenge'
        }
        self.data = {
            'method_name': 'Updated Method Name'
        }

        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_change_submission_data_and_visibility_when_submission_exist(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})
        self.data = {
            'method_name': 'Updated Method Name'
        }
        expected = {
                'id': self.submission.id,
                'participant_team': self.submission.participant_team.pk,
                'participant_team_name': self.submission.participant_team.team_name,
                'execution_time': self.submission.execution_time,
                'challenge_phase': self.submission.challenge_phase.pk,
                'created_by': self.submission.created_by.pk,
                'status': self.submission.status,
                'input_file': "http://testserver%s" % (self.submission.input_file.url),
                'method_name': self.data['method_name'],
                'method_description': self.submission.method_description,
                'project_url': self.submission.project_url,
                'publication_url': self.submission.publication_url,
                'stdout_file': None,
                'stderr_file': None,
                'submission_result_file': None,
                "submitted_at": "{0}{1}".format(self.submission.submitted_at.isoformat(), 'Z').replace("+00:00", ""),
                "is_public": self.submission.is_public,
                "when_made_public": "{0}{1}".format(self.submission.when_made_public.isoformat(),
                                                    'Z').replace("+00:00", ""),
            }
        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_submission_data_and_visibility_when_challenge_phase_is_private_and_user_is_host(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.private_challenge_phase.pk,
                                        'submission_pk': self.private_submission.pk})
        self.data = {
            'method_name': 'Updated Method Name'
        }

        expected = {
            'id': self.private_submission.id,
            'participant_team': self.private_submission.participant_team.pk,
            'participant_team_name': self.private_submission.participant_team.team_name,
            'execution_time': self.private_submission.execution_time,
            'challenge_phase': self.private_submission.challenge_phase.pk,
            'created_by': self.private_submission.created_by.pk,
            'status': self.private_submission.status,
            'input_file': "http://testserver%s" % (self.private_submission.input_file.url),
            'method_name': self.data['method_name'],
            'method_description': self.private_submission.method_description,
            'project_url': self.private_submission.project_url,
            'publication_url': self.private_submission.publication_url,
            'stdout_file': None,
            'stderr_file': None,
            'submission_result_file': None,
            "submitted_at": "{0}{1}".format(self.private_submission.submitted_at.isoformat(),
                                            'Z').replace("+00:00", ""),
            "is_public": self.private_submission.is_public,
            "when_made_public": "{0}{1}".format(self.private_submission.when_made_public.isoformat(),
                                                'Z').replace("+00:00", ""),
        }

        self.client.force_authenticate(user=self.user)

        self.challenge.participant_teams.add(self.host_participant_team)
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_submission_data_and_visibility_when_is_public_is_true(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})
        self.data = {
            'is_public': True
        }
        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_submission_data_and_visibility_when_is_public_is_false(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})
        self.data = {
            'is_public': False
        }
        expected = {
                'id': self.submission.id,
                'participant_team': self.submission.participant_team.pk,
                'participant_team_name': self.submission.participant_team.team_name,
                'execution_time': self.submission.execution_time,
                'challenge_phase': self.submission.challenge_phase.pk,
                'created_by': self.submission.created_by.pk,
                'status': self.submission.status,
                'input_file': "http://testserver%s" % (self.submission.input_file.url),
                'method_name': self.submission.method_name,
                'method_description': self.submission.method_description,
                'project_url': self.submission.project_url,
                'publication_url': self.submission.publication_url,
                'stdout_file': None,
                'stderr_file': None,
                'submission_result_file': None,
                "submitted_at": "{0}{1}".format(self.submission.submitted_at.isoformat(), 'Z').replace("+00:00", ""),
                "is_public": self.submission.is_public,
                "when_made_public": "{0}{1}".format(self.submission.when_made_public.isoformat(), 'Z')
                                    .replace("+00:00", ""),
            }
        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_submission_data_and_visibility_when_submission_doesnt_exist(self):
        self.url = reverse_lazy('jobs:change_submission_data_and_visibility',
                                kwargs={'challenge_pk': self.challenge.pk,
                                        'challenge_phase_pk': self.challenge_phase.pk,
                                        'submission_pk': self.submission.pk})

        expected = {
            'error': 'Submission does not exist'
        }
        self.data = {
            'method_name': 'Updated Method Name'
        }
        self.submission.delete()
        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.patch(self.url, self.data)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_submission_by_pk_when_submission_doesnt_exist(self):
        self.url = reverse_lazy('jobs:get_submission_by_pk',
                                kwargs={'submission_id': self.submission.id + 2})

        expected = {'error': 'Submission {} does not exist'.format(self.submission.id + 2)}

        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.get(self.url)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_submission_by_pk_when_user_created_the_submission(self):
        self.url = reverse_lazy('jobs:get_submission_by_pk',
                                kwargs={'submission_id': self.submission.id})
        expected = {
                'id': self.submission.id,
                'participant_team': self.submission.participant_team.pk,
                'participant_team_name': self.submission.participant_team.team_name,
                'execution_time': self.submission.execution_time,
                'challenge_phase': self.submission.challenge_phase.pk,
                'created_by': self.submission.created_by.pk,
                'status': self.submission.status,
                'input_file': "http://testserver%s" % (self.submission.input_file.url),
                'method_name': self.submission.method_name,
                'method_description': self.submission.method_description,
                'project_url': self.submission.project_url,
                'publication_url': self.submission.publication_url,
                'stdout_file': None,
                'stderr_file': None,
                'submission_result_file': None,
                "submitted_at": "{0}{1}".format(self.submission.submitted_at.isoformat(), 'Z').replace("+00:00", ""),
                "is_public": self.submission.is_public,
                "when_made_public": "{0}{1}".format(self.submission.when_made_public.isoformat(),
                                                    'Z').replace("+00:00", ""),
            }

        self.client.force_authenticate(user=self.submission.created_by)

        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.get(self.url)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_submission_by_pk_when_user_is_challenge_host(self):
        self.url = reverse_lazy('jobs:get_submission_by_pk',
                                kwargs={'submission_id': self.submission.id})
        expected = {
                'id': self.submission.id,
                'participant_team': self.submission.participant_team.pk,
                'participant_team_name': self.submission.participant_team.team_name,
                'execution_time': self.submission.execution_time,
                'challenge_phase': self.submission.challenge_phase.pk,
                'created_by': self.submission.created_by.pk,
                'status': self.submission.status,
                'input_file': "http://testserver%s" % (self.submission.input_file.url),
                'method_name': self.submission.method_name,
                'method_description': self.submission.method_description,
                'project_url': self.submission.project_url,
                'publication_url': self.submission.publication_url,
                'stdout_file': None,
                'stderr_file': None,
                'submission_result_file': None,
                "submitted_at": "{0}{1}".format(self.submission.submitted_at.isoformat(), 'Z').replace("+00:00", ""),
                "is_public": self.submission.is_public,
                "when_made_public": "{0}{1}".format(self.submission.when_made_public.isoformat(),
                                                    'Z').replace("+00:00", ""),
            }

        self.client.force_authenticate(user=self.user)

        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.get(self.url)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_submission_by_pk_when_user_is_neither_challenge_host_nor_submission_owner(self):
        self.url = reverse_lazy('jobs:get_submission_by_pk',
                                kwargs={'submission_id': self.submission.id})

        expected = {'error': 'Sorry, you are not authorized to access this submission.'}

        self.challenge.participant_teams.add(self.participant_team)
        response = self.client.get(self.url)
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ChallengeLeaderboardTest(BaseAPITestClass):

    def setUp(self):
        super(ChallengeLeaderboardTest, self).setUp()

        self.dataset_split = DatasetSplit.objects.create(
            name="Split 1",
            codename="split1"
        )

        self.challenge_phase_split = ChallengePhaseSplit.objects.create(
            challenge_phase=self.challenge_phase,
            dataset_split=self.dataset_split,
            leaderboard=self.leaderboard,
            visibility=ChallengePhaseSplit.PUBLIC
        )

        self.private_challenge_phase_split = ChallengePhaseSplit.objects.create(
            challenge_phase=self.private_challenge_phase,
            dataset_split=self.dataset_split,
            leaderboard=self.private_leaderboard,
            visibility=ChallengePhaseSplit.HOST
        )

        self.submission = Submission.objects.create(
            participant_team=self.participant_team,
            challenge_phase=self.challenge_phase,
            created_by=self.user1,
            status="submitted",
            input_file=self.challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/"
        )

        self.private_submission = Submission.objects.create(
            participant_team=self.host_participant_team,
            challenge_phase=self.private_challenge_phase,
            created_by=self.user,
            status="submitted",
            input_file=self.private_challenge_phase.test_annotation,
            method_name="Test Method",
            method_description="Test Description",
            project_url="http://testserver/",
            publication_url="http://testserver/"
        )

        self.submission.is_public = True
        self.submission.status = Submission.FINISHED
        self.submission.save()

        self.private_submission.is_public = True
        self.private_submission.status = Submission.FINISHED
        self.private_submission.save()

        self.result_json = {
            'score': 50.0,
            'test-score': 75.0
        }

        self.expected_results = [self.result_json['score'], self.result_json['test-score']]
        self.filtering_score = self.result_json[self.leaderboard.schema['default_order_by']]

        self.leaderboard_data = LeaderboardData.objects.create(
            challenge_phase_split=self.challenge_phase_split,
            submission=self.submission,
            leaderboard=self.leaderboard,
            result=self.result_json
        )

        self.private_leaderboard_data = LeaderboardData.objects.create(
            challenge_phase_split=self.private_challenge_phase_split,
            submission=self.private_submission,
            leaderboard=self.leaderboard,
            result=self.result_json
        )

    def test_get_leaderboard(self):
        self.url = reverse_lazy('jobs:leaderboard',
                                kwargs={'challenge_phase_split_id': self.challenge_phase_split.id})

        expected = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': self.leaderboard_data.id,
                    'submission__participant_team__team_name': self.submission.participant_team.team_name,
                    'challenge_phase_split': self.challenge_phase_split.id,
                    'result': self.expected_results,
                    'filtering_score': self.filtering_score,
                    'leaderboard__schema': {
                        'default_order_by': 'score',
                        'labels': ['score', 'test-score']
                    },
                    'submission__submitted_at': self.submission.submitted_at,
                }
            ]
        }
        expected = collections.OrderedDict(expected)

        response = self.client.get(self.url, {})

        self.assertEqual(response.data['count'], expected['count'])
        self.assertEqual(response.data['next'], expected['next'])
        self.assertEqual(response.data['previous'], expected['previous'])
        self.assertEqual(response.data['results'], expected['results'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_leaderboard_with_invalid_challenge_phase_split_id(self):
        self.url = reverse_lazy('jobs:leaderboard',
                                kwargs={'challenge_phase_split_id': self.challenge_phase_split.id + 2})

        expected = {'error': 'Challenge Phase Split does not exist'}

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_leaderboard_with_default_order_by_key_missing(self):
        self.url = reverse_lazy('jobs:leaderboard',
                                kwargs={'challenge_phase_split_id': self.challenge_phase_split.id})

        expected = {'error': 'Sorry, Default filtering key not found in leaderboard schema!'}

        leaderboard_schema = {
            'labels': ['score', 'test-score'],
        }
        self.leaderboard.schema = leaderboard_schema
        self.leaderboard.save()

        response = self.client.get(self.url, {})
        self.assertEqual(response.data, expected)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_leaderboard_for_host_submissions_on_private_challenge_phase(self):
        self.url = reverse_lazy('jobs:leaderboard',
                                kwargs={'challenge_phase_split_id': self.private_challenge_phase_split.id})

        expected = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                {
                    'id': self.private_leaderboard_data.id,
                    'submission__participant_team__team_name': self.private_submission.participant_team.team_name,
                    'challenge_phase_split': self.private_challenge_phase_split.id,
                    'result': self.expected_results,
                    'filtering_score': self.filtering_score,
                    'leaderboard__schema': {
                        'default_order_by': 'score',
                        'labels': ['score', 'test-score']
                    },
                    'submission__submitted_at': self.private_submission.submitted_at,
                }
            ]
        }

        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url, {})
        self.assertEqual(response.data['count'], expected['count'])
        self.assertEqual(response.data['next'], expected['next'])
        self.assertEqual(response.data['previous'], expected['previous'])
        self.assertEqual(response.data['results'], expected['results'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
