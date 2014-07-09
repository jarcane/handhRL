import shelve
import operator
from datetime import datetime

class HighScore:
    # a class for containing HighScores
    def __init__(self):
        # open our highscore file, and save the highscores to a class variable.
		# note, later on this variable might be saved in a gamestate class or
		# something similar. For now, we just create a new object whenver we
		# need the high scores, which reads them anew from the file.
        try:
            highScoreFile = shelve.open('highscore', 'r')
            self.highScores = highScoreFile['highscores']
            highScoreFile.close()
        except:
            # no file found or our key not found, make blank data.
            self.highScores = []
            
            sampleScore1 = {}
            sampleScore1['name'] = 'MaxMahem'
            sampleScore1['date'] = datetime.now()
            sampleScore1['score'] = 2
            
            sampleScore2 = {}
            sampleScore2['name'] = 'JArcane'
            sampleScore2['date'] = datetime.now()
            sampleScore2['score'] = 1
            
            self.highScores.append(sampleScore1)
            self.highScores.append(sampleScore2)
        
        self.sortScores()

    def display(self):
        # display our highscore list.      
        from handhrl import show_text_log
        
        self.sortScores()
        
        displayScores = []
        scoreCount = 1
        
        for score in self.highScores:
            displayScore = '{0}.'.format(scoreCount).ljust(3)
            displayScore += score['name'].ljust(15)
            displayScore += score['date'].strftime("%A, %d. %B %Y %I:%M%p").center(10)
            displayScore += str(score['score']).rjust(10)
            displayScores.append(displayScore)
            
			# break if we get over 10. Extra scores are retained however.
            scoreCount += 1
            if (scoreCount > 10):
                break
        
        show_text_log(displayScores)
    
    def addScore(self, score):
        # adds a score to our internal array, sorts it, and saves it.
        self.highScores.append(score)
        self.sortScores()
        
        highScoreFile = shelve.open('highscore', 'n')
        highScoreFile['highscores'] = self.highScores
        highScoreFile.close()

    def sortScores(self):
        # sort scores
        sortedHighScores = sorted(self.highScores, key=operator.itemgetter('score'), reverse=True)
        self.highScores = sortedHighScores
