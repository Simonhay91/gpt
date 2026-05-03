# Test Credentials

## Admin Account
- Email: `admin@ai.planetworkspace.com`
- Password: `Admin@123456`
- isAdmin: true

## Notes
- Reset path: ensure admin user exists in MongoDB `users` collection. `init_admin_user()` runs at backend startup.
- Login endpoint: `POST /api/auth/login`
