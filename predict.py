#!/usr/bin/python
# predict.py

################################################################################
# Imports
################################################################################
import os
import json
import pickle
import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

import numpy as np
from matplotlib import cm

from sklearn.pipeline import Pipeline
from sklearn.datasets.base import Bunch
from sklearn.metrics import classification_report
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import Imputer, LabelEncoder
from sklearn.base import BaseEstimator, TransformerMixin


################################################################################
# Ingestion
################################################################################
CENSUS_DATASET = (
    "http://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data",
    "http://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.names",
    "http://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test",
)

def download_data(path='data', urls=CENSUS_DATASET):
    if not os.path.exists(path):
        os.mkdir(path)

    for url in urls:
        response = requests.get(url)
        name = os.path.basename(url)
        with open(os.path.join(path, name), 'w') as f:
            f.write(response.text)      ####CHANGED FROM f.write(response.content)


################################################################################
# Load into Pandas
################################################################################
names = [
    'age',
    'workclass',
    'fnlwgt',
    'education',
    'education-num',
    'marital-status',
    'occupation',
    'relationship',
    'race',
    'sex',
    'capital-gain',
    'capital-loss',
    'hours-per-week',
    'native-country',
    'income',
]

data = pd.read_csv('data/adult.data', sep="\s*,", names=names, engine='python')
print (data.describe())             ####CHANGED FROM print data.describe()

###############################################################################
# Visualize
###############################################################################
sns.countplot(y='occupation', hue='income', data=data,)
sns.plt.show()

sns.countplot(y='education', hue='income', data=data,)
sns.plt.show()


# How years of education correlate to income, disaggregated by race. More education does not result in the same gains in income for Asian Americans/Pacific Islanders and Native Americans compared to Caucasians.
g = sns.FacetGrid(data, col='race', size=4, aspect=.5)
g = g.map(sns.boxplot, 'income', 'education-num')
sns.plt.show()

# How years of education correlate to income, disaggregated by sex. More education also does not result in the same gains in income for women compared to men.
g = sns.FacetGrid(data, col='sex', size=4, aspect=.5)
g = g.map(sns.boxplot, 'income', 'education-num')
sns.plt.show()

# How age correlates to income, disaggregated by race. Generally older people make more, except for Asian Americans/Pacific Islanders.
g = sns.FacetGrid(data, col='race', size=4, aspect=.5)
g = g.map(sns.boxplot, 'income', 'age')
sns.plt.show()

# How hours worked per week correlates to income, disaggregated by marital status.
g = sns.FacetGrid(data, col='marital-status', size=4, aspect=.5)
g = g.map(sns.boxplot, 'income', 'hours-per-week')
sns.plt.show()


sns.violinplot(x='sex', y='education-num', hue='income', data=data, split=True, scale='count')
sns.plt.show()

sns.violinplot(x='sex', y='hours-per-week', hue='income', data=data, split=True, scale='count')
sns.plt.show()

sns.violinplot(x='sex', y='age', hue='income', data=data, split=True, scale='count')
sns.plt.show()

g = sns.PairGrid(data,
                 x_vars=['income','sex'],
                 y_vars=['age'],
                 aspect=.75, size=3.5)
g.map(sns.violinplot, palette='pastel')
sns.plt.show()

g = sns.PairGrid(data,
                 x_vars=['marital-status','race'],
                 y_vars=['education-num'],
                 aspect=.75, size=3.5)
g.map(sns.violinplot, palette='pastel')
sns.plt.show()


def plot_classification_report(cr, title=None, cmap=cm.YlOrRd):
    title = title or 'Classification report'
    lines = cr.split('\n')
    classes = []
    matrix = []

    for line in lines[2:(len(lines)-3)]:
        s = line.split()
        classes.append(s[0])
        value = [float(x) for x in s[1: len(s) - 1]]
        matrix.append(value)

    fig, ax = plt.subplots(1)

    for column in range(len(matrix)+1):
        for row in range(len(classes)):
            txt = matrix[row][column]
            ax.text(column,row,matrix[row][column],va='center',ha='center')

    fig = plt.imshow(matrix, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    x_tick_marks = np.arange(len(classes)+1)
    y_tick_marks = np.arange(len(classes))
    plt.xticks(x_tick_marks, ['precision', 'recall', 'f1-score'], rotation=45)
    plt.yticks(y_tick_marks, classes)
    plt.ylabel('Classes')
    plt.xlabel('Measures')
    plt.show()


################################################################################
# Make the bunch
################################################################################
meta = {
    'target_names': list(data.income.unique()),
    'feature_names': list(data.columns),
    'categorical_features': {
        column: list(data[column].unique())
        for column in data.columns
        if data[column].dtype == 'object'
    },
}

with open('data/meta.json', 'w') as f:
    json.dump(meta, f, indent=2)

def load_data(root='data'):
    # Load the meta data from the file
    with open(os.path.join(root, 'meta.json'), 'r') as f:
        meta = json.load(f)

    names = meta['feature_names']

    # Load the readme information
    with open(os.path.join(root, 'README.md'), 'r') as f:
        readme = f.read()

    # Load the training and test data, skipping the bad row in the test data
    train = pd.read_csv(os.path.join(root, 'adult.data'), sep="\s*,", names=names, engine='python')
    test  = pd.read_csv(os.path.join(root, 'adult.test'), sep="\s*,", names=names, engine='python', skiprows=1)

    # Remove the target from the categorical features
    meta['categorical_features'].pop('income')

    # Return the bunch with the appropriate data chunked apart
    return Bunch(
        data = train[names[:-1]],
        target = train[names[-1]],
        data_test = test[names[:-1]],
        target_test = test[names[-1]],
        target_names = meta['target_names'],
        feature_names = meta['feature_names'],
        categorical_features = meta['categorical_features'],
        DESCR = readme,
    )

################################################################################
# Custom Label Encoder
################################################################################
class EncodeCategorical(BaseEstimator, TransformerMixin):
    """
    Encodes a specified list of columns or all columns if None.
    """

    def __init__(self, columns=None):
        self.columns  = columns
        self.encoders = None

    def fit(self, data, target=None):
        """
        Expects a data frame with named columns to encode.
        """
        # Encode all columns if columns is None
        if self.columns is None:
            self.columns = data.columns

        # Fit a label encoder for each column in the data frame
        self.encoders = {
            column: LabelEncoder().fit(data[column])
            for column in self.columns
        }
        return self

    def transform(self, data):
        """
        Uses the encoders to transform a data frame.
        """
        output = data.copy()
        for column, encoder in self.encoders.items():
            output[column] = encoder.transform(data[column])

        return output

################################################################################
# Custom Imputer for Missing Values
################################################################################
class ImputeCategorical(BaseEstimator, TransformerMixin):
    """
    Encodes a specified list of columns or all columns if None.
    """

    def __init__(self, columns=None):
        self.columns = columns
        self.imputer = None

    def fit(self, data, target=None):
        """
        Expects a data frame with named columns to impute.
        """
        # Encode all columns if columns is None
        if self.columns is None:
            self.columns = data.columns

        # Fit an imputer for each column in the data frame
        self.imputer = Imputer(missing_values=0, strategy='most_frequent')
        self.imputer.fit(data[self.columns])

        return self

    def transform(self, data):
        """
        Uses the encoders to transform a data frame.
        """
        output = data.copy()
        output[self.columns] = self.imputer.transform(output[self.columns])

        return output

################################################################################
# Pickle the Model for Future Use
################################################################################
def dump_model(model, path='data', name='classifier.pickle'):
    with open(os.path.join(path, name), 'wb') as f:
        pickle.dump(model, f)

################################################################################
# Command line Application
################################################################################
def load_model(path='data/classifier.pickle'):
    with open(path, 'rb') as f:
        return pickle.load(f)


def predict(model, meta=meta):
    data = {} # Store the input from the user

    for column in meta['feature_names'][:-1]:
        if column == 'fnlwgt':
            data[column] = 189778 # This is just the mean value.
        else:
            # Get the valid responses
            valid = meta['categorical_features'].get(column)

            # Prompt the user for an answer until good
            while True:
                val = " " + raw_input("enter {} >".format(column))
                if valid and val not in valid:
                    print "Not valid, choose one of {}".format(valid)
                else:
                    data[column] = val
                    break

    # Create prediction and label
    yhat = model.predict(pd.DataFrame([data]))
    print "We predict that you make %s" % yencode.inverse_transform(yhat)[0]


if __name__ == '__main__':
    # Get the data from the UCI repository
    download_data()

    # Load the data into a bunch object
    dataset = load_data()

    # Encode our target data
    yencode = LabelEncoder().fit(dataset.target)

    # Construct the pipeline
    census = Pipeline([
            ('encoder',  EncodeCategorical(dataset.categorical_features.keys())),
            ('imputer', ImputeCategorical(['workclass', 'native-country', 'occupation'])),
            ('classifier', LogisticRegression())
        ])

    # Fit the pipeline
    census.fit(dataset.data, yencode.transform(dataset.target))

    # Encode test targets, and strip trailing '.'
    y_true = yencode.transform([y.rstrip(".") for y in dataset.target_test])

    # Use the model to get the predicted value
    y_pred = census.predict(dataset.data_test)

    # execute classification report
    # print classification_report(y_true, y_pred, target_names=dataset.target_names)
    cr = classification_report(y_true, y_pred, target_names=dataset.target_names)
    print cr
    plot_classification_report(cr)

    # Pickle the model for future use
    dump_model(census)

    # Execute the command line interface
    model = load_model()
    predict(model)
