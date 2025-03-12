Features I want to add

	1. Add live scrobbles
	2. Database Live Stats (Under the Option Analytics in the Settings)
		Users: total user count
		Total Streams: total stream count from the databse
		Unique Tracks: total number of unique tracks in the db
		Unique Artists: total number of unique artists in the db
		Unique Albums: total number of unique albums in the db
	3. Database Optimization (low risk optimization, mostly tackling
		duplicates, without messing up any data counts)
	4. Try to combine the same songs. For example, sometimes artists drop albums, and then a deluxe album, and also singles, and the same song might be on all three with different covers, and sometimes that can count as three differnt songs in someone's listening history even though it is the same song.
	5. Ensure profile photo uploading works
	6. Figure out the artist/album/track pictures
	7. Mobile App Development
	8. Some sort of charts, that show listening history progression, on a track/album/artist basis.
	9. Profile Comparison (PDF export layout)
	10. Apple music compatibility
	11. Ads Integration. Use an ad network SDK (e.g. AdMob Mediation, Applovin MAX) to auction impressions among networks and boost eCPMSs
		Platform fees: Apple and Google dont take ad revenue cuts, they only charge fees on in-app purchases & subscriptions
		Serve ads ONLY to non-subscribers (subs get an ad-free experience)
		Track user behavior (ad impressions, eCPM, clicks) to optimize placement and frequency
		Keep SDK count low for simpler maintenance, and let mediation handle multiple ad sources
	12. Subscriptions
		Typical Fee: 30% for the first year on iOS/Android, then 15% in some cases
		Yearly vs Lifetime (this is a work in progress and isn't set in stone)
			Yearly Sub- $4.99
			Lifetime Sub(I want to give people the ability to buy a lifetime sub, not sure how much this shuold cost, $14.99, $19.99, $24.99?)
				Have to take into account total revenue, retention, engagement over time
		
Implementation Details and Rationale
Phase 1: Core Functionality Improvements
1. Fix Profile Photo Uploading (#5)
The implementation exists but needs troubleshooting - most likely there are issues with file permissions or the file path handling
This is a quick win that provides immediate user value
I recommend implementing unique filenames using timestamps or UUIDs to prevent conflicts
2. Implement Artist/Album/Track Pictures (#6)
This builds upon the same image handling infrastructure as profile photos
Addressing both image issues together creates a cohesive visual experience
The database already has image_url fields in relevant tables
Phase 2: Data Quality and Performance
3. Database Optimization (#3)
The database requires optimizing for duplicates without losing data integrity
This foundation work will ensure subsequent features run efficiently
Implementing strategic indexes can significantly improve query performance
4. Song Combination/Deduplication (#4)
This extends the optimization work, creating a more accurate representation of listening habits
Requires careful metadata matching algorithms to identify same songs with different releases
Important to complete before implementing visualization features for accurate reporting
5. Database Live Stats (#2)
Provides valuable analytics data using the newly optimized database
Relatively straightforward implementation of count queries
Creates a sense of community by showing overall platform metrics
Phase 3: Enhanced User Experience
6-8. Charts, Profile Comparison, and Live Scrobbles
These features enhance user engagement after core functionality is solid
Live scrobbles will need webhook integrations with streaming platforms
Profile comparison adds social value that encourages platform growth
Phase 4-5: Platform Expansion and Monetization
The final phases focus on expanding to new platforms and implementing monetization features that will sustain the project long-term.
Would you like me to elaborate on any specific feature implementation or the rationale behind this ordering?