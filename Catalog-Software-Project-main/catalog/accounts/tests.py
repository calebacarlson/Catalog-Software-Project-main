from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.utils import ErrorDict
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from .admin import (
	CustomUserAdmin,
	CustomUserChangeForm,
	CustomUserCreationForm,
	RoleAdmin,
	RoleAdminForm,
	SchoolAdmin,
)
from catalog.middleware import AdminAccessMiddleware
from .decorators import permission_required, role_level_required
from .models import Role, School, University, User
from .views import admin_catalog_view, catalog_view


class PermissionModelCheckpointTests(TestCase):
	def setUp(self):
		self.university_a = University.objects.create(name='Stanford', slug='stanford')
		self.university_b = University.objects.create(name='MIT', slug='mit')

	def test_user_school_must_belong_to_the_same_university(self):
		school = School.objects.create(name='Business', university=self.university_a)
		user = User(email='test@mit.edu', university=self.university_b, school=school)

		with self.assertRaises(ValidationError) as error:
			user.full_clean()

		self.assertIn('school', error.exception.message_dict)

	def test_role_rejects_unknown_permissions(self):
		role = Role(name='Bad Role', permissions=['invalid.perm'])

		with self.assertRaises(ValidationError) as error:
			role.full_clean()

		self.assertIn('permissions', error.exception.message_dict)

	def test_user_permissions_follow_assigned_role(self):
		role = Role(
			name='Viewer',
			university=self.university_a,
			permissions=['catalog.view'],
		)
		user = User(email='viewer@stanford.edu', university=self.university_a, role=role)

		self.assertTrue(user.has_perm('catalog.view'))
		self.assertFalse(user.has_perm('catalog.delete'))


class PermissionEnforcementCheckpointTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def test_permission_decorator_denies_missing_permission(self):
		request = self.factory.get('/test/')
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			role=SimpleNamespace(has_permission=lambda permission: False),
		)

		@permission_required('catalog.edit')
		def view(_request):
			return 'OK'

		with self.assertRaises(PermissionDenied):
			view(request)

	def test_permission_decorator_allows_superuser(self):
		request = self.factory.get('/test/')
		request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

		@permission_required('catalog.edit')
		def view(_request):
			return 'OK'

		self.assertEqual(view(request), 'OK')

	def test_role_level_decorator_enforces_maximum_level(self):
		request = self.factory.get('/test/')
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			role=SimpleNamespace(level=4),
		)

		@role_level_required(3)
		def view(_request):
			return 'OK'

		with self.assertRaises(PermissionDenied):
			view(request)

	def test_admin_middleware_rejects_role_without_valid_permissions(self):
		request = self.factory.get('/app-admin/')
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			is_staff=True,
			role=SimpleNamespace(permissions=['invalid.permission'], name='Empty'),
			university=object(),
			email='staff@example.edu',
		)
		middleware = AdminAccessMiddleware(lambda _request: HttpResponse('OK'))

		response = middleware(request)

		self.assertEqual(response.status_code, 403)
		self.assertEqual(
			response.content,
			b'Access denied. Your role has no active permissions.',
		)


class AdminPermissionCheckpointTests(SimpleTestCase):
	def setUp(self):
		self.university_id = 'tenant-1'
		role = SimpleNamespace(
			level=2,
			permissions=['roles.view', 'roles.edit', 'users.view', 'schools.view'],
		)
		role.has_permission = lambda permission: permission in role.permissions
		self.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			is_staff=True,
			role=role,
			university=SimpleNamespace(id=self.university_id),
		)
		self.request = SimpleNamespace(
			user=self.user,
			scoped_university=self.user.university,
		)

	def test_role_form_rejects_permissions_outside_creator_subset(self):
		self.user.role.permissions = ['catalog.view']
		form = RoleAdminForm(
			data={
				'name': 'Child',
				'permissions': ['catalog.edit'],
			},
			request_user=self.user,
		)

		self.assertFalse(form.is_valid())
		self.assertIn('permissions', form.errors)

	def test_role_form_only_exposes_name_and_permissions(self):
		form = RoleAdminForm(request_user=self.user)

		self.assertEqual(set(form.fields), {'name', 'permissions'})
		role_admin = RoleAdmin(Role, admin.site)
		fieldsets = role_admin.get_fieldsets(self.request)
		self.assertEqual(set(fieldsets[0][1]['fields']), {'name', 'permissions'})
		self.assertTrue(
			{code for code, _label in form.fields['permissions'].choices}
			<= set(self.user.role.permissions)
		)

	def test_role_admin_auto_assigns_creator_level_plus_one(self):
		role_admin = RoleAdmin(Role, admin.site)
		new_role = Role(name='Department Coordinator')
		university = University(name='Stanford', slug='stanford')
		self.request.scoped_university = university
		self.user.is_superuser = False

		with patch('django.contrib.admin.ModelAdmin.save_model'):
			role_admin.save_model(self.request, new_role, form=None, change=False)

		self.assertEqual(new_role.level, 3)
		self.assertEqual(new_role.university, university)

	def test_role_admin_increments_level_three_creator_to_level_four(self):
		role_admin = RoleAdmin(Role, admin.site)
		new_role = Role(name='Assistant')
		university = University(name='Stanford', slug='stanford')
		self.request.scoped_university = university
		self.user.role.level = 3

		with patch('django.contrib.admin.ModelAdmin.save_model'):
			role_admin.save_model(self.request, new_role, form=None, change=False)

		self.assertEqual(new_role.level, 4)
		self.assertEqual(new_role.university, university)

	def test_role_admin_assigns_level_two_to_superuser_roles(self):
		role_admin = RoleAdmin(Role, admin.site)
		new_role = Role(name='Campus Admin')
		superuser_request = SimpleNamespace(
			user=SimpleNamespace(is_superuser=True, role=None),
		)

		with patch('django.contrib.admin.ModelAdmin.save_model'):
			role_admin.save_model(superuser_request, new_role, form=None, change=False)

		self.assertEqual(new_role.level, 2)

	def test_role_admin_requires_edit_permission_and_subordinate_role(self):
		role_admin = RoleAdmin(Role, admin.site)
		role = SimpleNamespace(university_id=self.university_id, level=3)

		self.assertTrue(role_admin.has_change_permission(self.request, role))
		role.level = 2
		self.assertFalse(role_admin.has_change_permission(self.request, role))
		self.user.role.permissions = ['roles.view']
		self.assertFalse(role_admin.has_change_permission(self.request, role))

	def test_school_admin_requires_school_permissions(self):
		school_admin = SchoolAdmin(School, admin.site)
		self.user.role.permissions = ['schools.view']
		self.assertTrue(school_admin.has_module_permission(self.request))
		self.assertFalse(school_admin.has_add_permission(self.request))
		self.user.role.permissions = ['schools.add']
		self.assertTrue(school_admin.has_add_permission(self.request))

	def test_user_admin_scopes_objects_and_hides_role_assignment(self):
		user_admin = CustomUserAdmin(User, admin.site)
		self.user.role.permissions = ['users.view']
		local_user = SimpleNamespace(is_superuser=False, university_id=self.university_id)
		other_user = SimpleNamespace(is_superuser=False, university_id='tenant-2')

		self.assertTrue(user_admin.has_view_permission(self.request, local_user))
		self.assertFalse(user_admin.has_view_permission(self.request, other_user))
		self.assertFalse(user_admin.has_add_permission(self.request))
		self.assertNotIn(
			'role',
			user_admin.get_fieldsets(self.request)[0][1]['fields'],
		)
		self.assertIn(
			'school',
			user_admin.get_fieldsets(self.request)[0][1]['fields'],
		)

		self.user.role.permissions = ['users.edit']
		self.assertTrue(user_admin.has_change_permission(self.request, local_user))


class SchoolScopeCheckpointTests(SimpleTestCase):
	def setUp(self):
		self.university = University(name='Stanford', slug='stanford')
		self.school = School(name='Business', university=self.university)
		self.user = SimpleNamespace(
			is_superuser=False,
			role=SimpleNamespace(level=3),
			school=self.school,
			school_id='school-a',
		)
		self.request = SimpleNamespace(
			user=self.user,
			scoped_university=self.university,
		)

	def test_creation_and_change_forms_require_school_for_level_three_role(self):
		for form_class in (CustomUserCreationForm, CustomUserChangeForm):
			form = form_class()
			form.cleaned_data = {'role': SimpleNamespace(level=3), 'school': None}
			form._errors = ErrorDict()

			form.clean()

			self.assertIn('school', form.errors)
			self.assertIn('School assignment is required', str(form.errors['school']))

	def test_creation_form_accepts_level_three_role_with_school(self):
		form = CustomUserCreationForm()
		form.cleaned_data = {'role': SimpleNamespace(level=3), 'school': self.school}
		form._errors = ErrorDict()

		form.clean()

		self.assertNotIn('school', form.errors)

	def test_school_admin_user_queryset_is_limited_to_assigned_school(self):
		user_admin = CustomUserAdmin(User, admin.site)
		base_queryset = Mock()
		tenant_queryset = Mock()
		school_queryset = Mock()
		base_queryset.filter.return_value = tenant_queryset
		tenant_queryset.filter.return_value = school_queryset

		with patch('django.contrib.admin.ModelAdmin.get_queryset', return_value=base_queryset):
			result = user_admin.get_queryset(self.request)

		self.assertIs(result, school_queryset)
		base_queryset.filter.assert_called_once_with(
			university=self.university,
			is_superuser=False,
		)
		tenant_queryset.filter.assert_called_once_with(school=self.school)

	def test_school_admin_without_school_sees_no_users(self):
		user_admin = CustomUserAdmin(User, admin.site)
		self.user.school = None
		base_queryset = Mock()
		tenant_queryset = Mock()
		empty_queryset = Mock()
		base_queryset.filter.return_value = tenant_queryset
		tenant_queryset.none.return_value = empty_queryset

		with patch('django.contrib.admin.ModelAdmin.get_queryset', return_value=base_queryset):
			result = user_admin.get_queryset(self.request)

		self.assertIs(result, empty_queryset)

	def test_school_admin_is_auto_assigned_to_new_user(self):
		user_admin = CustomUserAdmin(User, admin.site)
		new_user = User(email='new@stanford.edu')

		with patch('django.contrib.admin.ModelAdmin.save_model'):
			user_admin.save_model(self.request, new_user, form=None, change=False)

		self.assertIs(new_user.university, self.university)
		self.assertIs(new_user.school, self.school)

	def test_school_dropdown_is_limited_to_assigned_school(self):
		user_admin = CustomUserAdmin(User, admin.site)
		db_field = SimpleNamespace(name='school')
		queryset = Mock()
		with patch.object(School.objects, 'filter', return_value=queryset) as school_filter:
			with patch(
				'django.contrib.admin.ModelAdmin.formfield_for_foreignkey',
				return_value='school-form-field',
			):
				result = user_admin.formfield_for_foreignkey(db_field, self.request)

		self.assertEqual(result, 'school-form-field')
		school_filter.assert_called_once_with(id=self.user.school_id)


class CatalogViewPermissionTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.university = SimpleNamespace(slug='stanford')
		self.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			university=self.university,
			role=SimpleNamespace(
				has_permission=lambda permission: permission in {'catalog.view', 'catalog.edit'},
			),
		)

	def test_catalog_view_rejects_user_without_view_permission(self):
		self.user.role.has_permission = lambda _permission: False
		request = self.factory.get('/stanford/catalog/')
		request.user = self.user

		with self.assertRaises(PermissionDenied):
			catalog_view(request, university_slug='stanford')

	def test_catalog_view_keeps_tenant_isolation(self):
		request = self.factory.get('/mit/catalog/')
		request.user = self.user
		other_university = SimpleNamespace(slug='mit')

		with patch('accounts.views.get_object_or_404', return_value=other_university):
			response = catalog_view(request, university_slug='mit')

		self.assertEqual(response.status_code, 403)

	def test_admin_catalog_view_requires_edit_permission(self):
		self.user.role.has_permission = lambda permission: permission == 'catalog.view'
		request = self.factory.get('/admin-catalog/')
		request.user = self.user

		with self.assertRaises(PermissionDenied):
			admin_catalog_view(request)

# Risk Assessment for Step 3
# Risk	Likelihood	Impact
# Missing is_superuser=False filter in queryset	Medium (easy to forget)	Information leak
# get_fieldsets() includes is_superuser for campus admin	Would be critical if present	Privilege escalation
# has_change_permission returning True without object check	Common mistake	Direct URL bypass
# RoleAdmin left unprotected	Certain if not addressed	Permission escalation via role editing
# is_staff toggle left visible to campus admin	Depends on your decision	Campus admins can create more staff

# Test	Expected
# Campus admin visits /campus-admin/stanford/accounts/user/	Only Stanford non-superusers appear
# Campus admin opens any user's edit form	No is_superuser or is_staff fields visible in DOM
# Campus admin uses dev tools to inject is_superuser=on and submits	Field silently ignored; user not promoted
# Campus admin types /campus-admin/stanford/accounts/user/1/change/ where user 1 is a superuser	403 Forbidden
# Campus admin types /campus-admin/stanford/accounts/user/<mit_user_id>/change/	403 Forbidden
# Superuser visits /app-admin/accounts/user/	Sees everything, including is_superuser field

# The dev-tools injection test is the critical one — it validates that get_fieldsets() is working as a security boundary, not just a UI filter.

# 7. list_filter leaks information
# Your current list_filter = ('is_staff', 'is_superuser', 'is_active', 'university', 'role') is shown to all admins. A campus admin would see:

# A university filter dropdown listing every university in the system (information leak)
# An is_superuser filter that, when clicked, would show zero results (because get_queryset filters them out) but confirms superusers exist
# Recommendation (future hardening): Override get_list_filter() to return a scoped filter list for non-superusers. Not security-critical since get_queryset() enforces the actual filter, but it's an information leak worth closing.

# Tests for Step 6:
# Superuser login	is_superuser=True, university=None	Redirect to /app-admin/
# Campus admin login	is_staff=True, role=<set>, university=<X>	Redirect to /campus-admin/<X.slug>/
# Regular user login	is_staff=False, role=None, university=<X>	Redirect to /<X.slug>/catalog/
# Staff with no role	`is_staff=True, role=None, university=