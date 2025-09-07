# Payment Implementation for Songs

## Overview
This implementation adds a freemium model to the song generation feature:
- Users can create their first 3 songs for free
- Starting from the 4th song, users need to pay 10 Telegram Stars to unlock each song

## Implementation Details

### Database Changes
1. Added a new method `get_user_song_count(user_uuid)` to [database.py](database.py) that counts the number of songs a user has created:
   ```python
   def get_user_song_count(self, user_uuid: str) -> int:
       """Get the number of songs created by a user."""
       result = self.query_one(
           "SELECT COUNT(*) as song_count FROM songs WHERE user_id = %s",
           (user_uuid,)
       )
       return result["song_count"] if result else 0
   ```

### Suno Manager Changes
In [suno_manager.py](suno_manager.py), the `handle_suno_callback` method was modified to:

1. Check how many songs the user has already created:
   ```python
   song_count = self.db.get_user_song_count(user_uuid)
   is_free_song = song_count < 3
   ```

2. For free songs (first 3):
   - Send the audio file directly to the user
   - Add a "Ваша песня готова! 🎧 (Бесплатно)" caption

3. For paid songs (4th and beyond):
   - Send a locked audio message with payment buttons
   - Create a payment record in the database
   - Use the message "🔒 Ваша песня готова! Разблокируйте за 10 звезд:"

### Test Coverage
The implementation includes tests in [test_payment.py](test_payment.py) that verify:
- The free song logic (first 3 songs are free, 4th+ require payment)
- The database method exists

## User Experience
- Users will see a clear message indicating whether their song is free or requires payment
- The first 3 songs are completely free with no payment required
- Starting from the 4th song, users will need to pay 10 Telegram Stars to unlock each song

## Database Migration
No database migration is required as we're only adding a new method that uses existing tables.

## Future Improvements
- Add configuration option for the free song limit (currently hardcoded to 3)
- Add configuration option for the payment amount (currently hardcoded to 10 stars)
- Add analytics to track how many users hit the free limit