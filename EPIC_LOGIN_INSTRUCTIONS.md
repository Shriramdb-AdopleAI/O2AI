# Epic Login Instructions

## Important: How Epic OAuth Login Works

When you click "Login with Epic" in our app:

1. ✅ **You get redirected to Epic's login page** (this is working!)
2. ⚠️ **You need to use YOUR Epic credentials** (not app credentials)
3. ✅ **After login, Epic redirects back to our app**

## What Credentials to Use

### On the Epic Login Page (HYPERSPACE):

You need to use **Epic system credentials**, not your app credentials.

**If you have Epic access:**
- **User ID:** Your Epic User ID (e.g., `O2aicorp` or your actual Epic username)
- **Password:** Your Epic password (e.g., `abcd@1234P` or your actual Epic password)

**If you DON'T have Epic credentials:**
- You need to contact your Epic administrator
- They need to provide you with Epic system access
- Epic OAuth requires valid Epic user credentials

## Common Issues

### Issue 1: "Invalid User ID or Password"

**Cause:** The credentials you're using are not valid Epic credentials.

**Solution:**
1. Verify you're using Epic system credentials (not app credentials)
2. Contact your Epic administrator to get correct credentials
3. Make sure your Epic account is active

### Issue 2: "Access Denied"

**Cause:** Your Epic account doesn't have permission to use this app.

**Solution:**
1. Contact your Epic administrator
2. Ask them to grant your Epic user access to the OAuth app
3. Verify the app is approved in Epic App Orchard

### Issue 3: Login Works But Redirect Fails

**Cause:** Redirect URI mismatch or backend issue.

**Solution:**
1. Check console for error messages
2. Verify redirect URI matches Epic App Orchard exactly
3. Check backend logs for token exchange errors

## Testing Epic Login

### Step 1: Click "Login with Epic"
- You should be redirected to Epic's login page

### Step 2: Enter Epic Credentials
- **User ID:** Your Epic username
- **Password:** Your Epic password
- Click "Log In"

### Step 3: Authorize the App
- Epic may ask you to authorize the app
- Click "Allow" or "Authorize"

### Step 4: Return to App
- Epic redirects you back to our app
- You should be logged in

## Getting Epic Credentials

If you don't have Epic credentials:

1. **Contact Epic Administrator:**
   - They can create an Epic user account for you
   - They can grant access to the OAuth app

2. **Check with Your Organization:**
   - Your IT department may have Epic access
   - They can provide credentials or create an account

3. **Epic Support:**
   - If you're the app owner, contact Epic support
   - They can help with user access and credentials

## Important Notes

- **Epic credentials are different from app credentials**
- **You need valid Epic system access to use OAuth**
- **The login page you see is Epic's official login page**
- **If credentials don't work, it's an Epic account issue, not an app issue**

## Error Messages Explained

### "Invalid User ID or Password"
- Your Epic credentials are incorrect
- Contact Epic administrator for correct credentials

### "Access Denied" 
- Your Epic account doesn't have permission
- Contact Epic administrator to grant access

### "Invalid Client"
- Client ID issue (not a credential problem)
- Check VITE_EPIC_CLIENT_ID in .env

### "Invalid Scope"
- Scopes not approved in Epic App Orchard
- Check approved scopes in Epic App Orchard

## Still Having Issues?

1. **Verify Epic Credentials:**
   - Try logging into Epic directly (not through OAuth)
   - If that doesn't work, credentials are wrong

2. **Check Epic App Orchard:**
   - Verify app is approved
   - Check if your Epic user has access

3. **Contact Epic Support:**
   - They can verify your account status
   - They can check app configuration

