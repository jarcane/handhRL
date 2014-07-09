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
            highscorefile = shelve.open('highscore', 'r')
            self.highScores = highscorefile['highscores']
            highscorefile.close()
        except:
            # no file found or our key not found, make blank data.
            self.highScores = []

            samplescore1 = {'name': 'MaxMahem', 'date': datetime.now(), 'score': 2}

            samplescore2 = {'name': 'JArcane', 'date': datetime.now(), 'score': 1}

            self.highScores.append(samplescore1)
            self.highScores.append(samplescore2)

        self.sortscores()

    def display(self):
        # display our highscore list.      
        from handhrl import show_text_log

        self.sortscores()

        displayscores = []
        scorecount = 1

        for score in self.highScores:
            displayscore = '{0}.'.format(scorecount).ljust(3)
            displayscore += score['name'].ljust(15)
            displayscore += score['date'].strftime("%A, %d. %B %Y %I:%M%p").center(10)
            displayscore += str(score['score']).rjust(10)
            displayscores.append(displayscore)

            # break if we get over 10. Extra scores are retained however.
            scorecount += 1
            if scorecount > 10:
                break

        show_text_log(displayscores)

    def addscore(self, score):
        # adds a score to our internal array, sorts it, and saves it.
        self.highScores.append(score)
        self.sortscores()

        highscorefile = shelve.open('highscore', 'n')
        highscorefile['highscores'] = self.highScores
        highscorefile.close()

    def sortscores(self):
        # sort scores
        sortedhighscores = sorted(self.highScores, key=operator.itemgetter('score'), reverse=True)
        self.highScores = sortedhighscores
