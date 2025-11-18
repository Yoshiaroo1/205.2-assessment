import numpy as np
import xgboost as xgb

class ETAModel:
    def __init__(self):
        self.model = xgb.XGBRegressor()
        self.trained = False

    def train(self, X, y):
        self.model.fit(X, y)
        self.trained = True

    def predict(self, distance, hour, day):
        if not self.trained:
            # fallback = 40 km/h average speed
            return (distance / 40) * 60
        X = np.array([[distance, hour, day]])
        return float(self.model.predict(X)[0])
