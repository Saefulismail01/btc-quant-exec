import numpy as np
import time
from hmmlearn.hmm import GMMHMM

def test_gmmhmm():
    print("Generating synthetic data...")
    # Generate random features: 2000 rows, 8 features
    np.random.seed(42)
    X = np.random.randn(2000, 8)
    
    n_components = 4
    n_mix = 2
    
    print(f"Initializing GMMHMM (n_components={n_components}, n_mix={n_mix})...")
    model = GMMHMM(
        n_components=n_components,
        n_mix=n_mix,
        covariance_type="full",
        n_iter=1000,
        random_state=42,
        init_params="stmcw",
        verbose=True
    )
    from sklearn.mixture import GaussianMixture
    
    print("Pre-fitting GaussianMixture to manual-init GMMHMM...")
    # Pre-calculate components using Sklearn (which avoids the hmmlearn joblib hang)
    gmm = GaussianMixture(n_components=n_mix, covariance_type="full", random_state=42)
    
    # We need n_components * n_mix means. 
    # Let's just create random weights/means/covars properly shaped.
    # The real fix for the hang is passing init_params='st' and explicitly setting parameters.
    model.init_params = "st"
    model.weights_ = np.ones((n_components, n_mix)) / n_mix
    model.means_ = np.random.randn(n_components, n_mix, X.shape[1])
    
    # Generate positive definite covariance matrices
    covars = np.zeros((n_components, n_mix, X.shape[1], X.shape[1]))
    for c in range(n_components):
        for m_idx in range(n_mix):
            covars[c, m_idx] = np.eye(X.shape[1])
            
    model.covars_ = covars

    print("Fitting model...")
    t0 = time.time()
    model.fit(X)
    t1 = time.time()
    
    print(f"Fit complete in {t1 - t0:.2f} seconds.")
    
    # Calculate BIC parameters
    k = model.n_components
    m = model.n_mix
    n_features = X.shape[1]
    n_params = k * (k - 1) + k * (m - 1) + k * m * n_features + k * m * n_features * (n_features + 1) / 2
    
    log_lik = model.score(X) * len(X)
    bic = -2 * log_lik + n_params * np.log(len(X))
    
    print(f"Params: {n_params:.1f} | BIC: {bic:.1f}")

if __name__ == "__main__":
    test_gmmhmm()
